from __future__ import annotations

import io

from docx import Document
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from job_hunter.api.schemas import ConfigOut, ResumeVersionOut, TailorRequest, TailorResponse
from job_hunter.auth import AuthUser, get_current_user
from job_hunter.config import GroqConfig
from job_hunter.docx_tailor import tailor_docx
from job_hunter.resume_profile import docx_to_text, extract_profile
from job_hunter.resume_store import ResumeNotFoundError, ResumeStore

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def get_resume_store(request: Request) -> ResumeStore:
    return request.app.state.resume_store


def get_groq_config(request: Request):
    return request.app.state.config.groq


def _update_candidate_profile(
    store: ResumeStore,
    groq_config: GroqConfig,
    user_id: str,
    docx_bytes: bytes,
    version_id: str,
) -> None:
    """Best-effort profile refresh; never fails the calling request."""
    try:
        profile = extract_profile(docx_to_text(docx_bytes), groq_config)
        store.upsert_candidate_profile(user_id, profile, source_version_id=version_id)
    except Exception as exc:
        print(f"candidate profile update failed for user {user_id}: {exc}")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config", response_model=ConfigOut)
def get_config(request: Request) -> ConfigOut:
    storage = request.app.state.config.storage
    if not storage.supabase_url or not storage.supabase_publishable_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not configured with SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY.",
        )
    return ConfigOut(
        supabase_url=storage.supabase_url,
        supabase_publishable_key=storage.supabase_publishable_key,
    )


@router.post("/resumes", response_model=ResumeVersionOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: AuthUser = Depends(get_current_user),
    store: ResumeStore = Depends(get_resume_store),
    groq_config: GroqConfig = Depends(get_groq_config),
) -> ResumeVersionOut:
    if file.content_type not in DOCX_CONTENT_TYPES and not (file.filename or "").lower().endswith(
        ".docx"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx resumes are supported.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume file is too large (max 5MB).",
        )
    try:
        Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is not a valid .docx document: {exc}",
        ) from exc

    row = store.create_upload_version(
        user_id=current_user.id,
        file_bytes=file_bytes,
        original_filename=file.filename or "resume.docx",
    )
    _update_candidate_profile(store, groq_config, current_user.id, file_bytes, row["id"])
    return ResumeVersionOut.from_row(row)


@router.get("/resumes", response_model=list[ResumeVersionOut])
def list_resumes(
    current_user: AuthUser = Depends(get_current_user),
    store: ResumeStore = Depends(get_resume_store),
) -> list[ResumeVersionOut]:
    rows = store.list_versions(current_user.id)
    return [ResumeVersionOut.from_row(row) for row in rows]


@router.get("/resumes/{version_id}/download")
def download_resume(
    version_id: str,
    current_user: AuthUser = Depends(get_current_user),
    store: ResumeStore = Depends(get_resume_store),
) -> StreamingResponse:
    try:
        data, version = store.download_bytes(current_user.id, version_id)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    filename = version["original_filename"]
    return StreamingResponse(
        io.BytesIO(data),
        media_type=version["mime_type"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/resumes/tailor", response_model=TailorResponse)
def tailor_resume(
    body: TailorRequest,
    current_user: AuthUser = Depends(get_current_user),
    store: ResumeStore = Depends(get_resume_store),
    groq_config=Depends(get_groq_config),
) -> TailorResponse:
    if body.source_version_id:
        try:
            source_version = store.get_version(current_user.id, body.source_version_id)
        except ResumeNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    else:
        source_version = store.get_current_version(current_user.id)
        if source_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No resume uploaded yet. Upload one before tailoring.",
            )

    original_bytes, _ = store.download_bytes(current_user.id, source_version["id"])

    skills = body.skills
    if not skills:
        profile_row = store.get_candidate_profile(current_user.id)
        if profile_row:
            skills = profile_row.get("skills") or []

    result = tailor_docx(
        original_bytes=original_bytes,
        job_title=body.job_title,
        job_description=body.job_description,
        matched_skills=skills,
        profile_skills=skills,
        groq_config=groq_config,
    )

    if not result.changed:
        return TailorResponse(changed=False, version=None, suggestion=result.suggestion.to_dict())

    new_row = store.create_tailored_version(
        user_id=current_user.id,
        source_version=source_version,
        file_bytes=result.docx_bytes,
        job_title=body.job_title,
        job_description=body.job_description,
        job_id=body.job_id,
        tailoring_mode=result.mode,
        suggestion=result.suggestion,
        fit_score=result.fit_score,
    )
    _update_candidate_profile(
        store, groq_config, current_user.id, result.docx_bytes, new_row["id"]
    )
    return TailorResponse(
        changed=True,
        version=ResumeVersionOut.from_row(new_row),
        suggestion=result.suggestion.to_dict(),
    )
