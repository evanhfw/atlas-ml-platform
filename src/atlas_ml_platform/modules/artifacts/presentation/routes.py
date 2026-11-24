from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Request, Response, UploadFile, status

from atlas_ml_platform.api.dependencies import ArtifactStoreDep, UnitOfWorkDep
from atlas_ml_platform.modules.artifacts.application import (
    ArtifactTooLarge,
    DownloadArtifact,
    GetArtifact,
    UploadArtifact,
    UploadArtifactCommand,
)
from atlas_ml_platform.modules.artifacts.presentation.schemas import ArtifactRead

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

_UPLOAD_CHUNK_SIZE = 1024 * 1024


async def _read_upload_limited(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
        total += len(chunk)
        if total > max_size_bytes:
            raise ArtifactTooLarge(max_size_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    request: Request,
    file: Annotated[UploadFile, File()],
    uow: UnitOfWorkDep,
    store: ArtifactStoreDep,
) -> ArtifactRead:
    settings = request.app.state.settings
    data = await _read_upload_limited(file, settings.ARTIFACT_MAX_SIZE_BYTES)
    artifact = await UploadArtifact(
        uow,
        store,
        max_size_bytes=settings.ARTIFACT_MAX_SIZE_BYTES,
    ).execute(
        UploadArtifactCommand(
            data=data,
            content_type=file.content_type or "application/octet-stream",
        )
    )
    return ArtifactRead.from_domain(artifact)


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(artifact_id: UUID, uow: UnitOfWorkDep) -> ArtifactRead:
    artifact = await GetArtifact(uow).execute(artifact_id)
    return ArtifactRead.from_domain(artifact)


@router.get("/{artifact_id}/content")
async def download_artifact(
    artifact_id: UUID,
    uow: UnitOfWorkDep,
    store: ArtifactStoreDep,
) -> Response:
    artifact, data = await DownloadArtifact(uow, store).execute(artifact_id)
    return Response(
        content=data,
        media_type=artifact.content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.id}"'},
    )
