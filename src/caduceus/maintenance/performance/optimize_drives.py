"""
Otimizar unidades

Cruza cada volume fixo com a sua partição e com o disco físico indicado pelo Windows. Só corre
TRIM ou desfragmentação se o tipo for conhecido e voltar a ser confirmado ao iniciar a ação.
"""

import base64
import json
import re
from dataclasses import dataclass

from caduceus.maintenance.actions import Action, Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.powershell import run_powershell, run_powershell_with_progress

_DRIVE_LETTER = re.compile(r"[A-Z]")
_OPERATIONS = {"SSD": "-ReTrim", "HDD": "-Defrag"}

# O número de Get-Disk e o DeviceId de Get-PhysicalDisk não pertencem ao mesmo espaço de nomes.
# Um disco virtual, RAID ou de espaços de armazenamento pode ter vários suportes por trás.
_DETECT_MEDIA = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$disks = @(Get-Disk)
$physicalDisks = @(Get-PhysicalDisk)
$directBusTypes = '1', '3', '7', '10', '11', '17', 'SCSI', 'ATA', 'USB', 'SAS', 'SATA', 'NVMe'

function Get-DriveMediaType($volume) {
    if ([string]$volume.DriveType -notin 'Fixed', '3') { return }
    $partitions = @(Get-Partition -Volume $volume -ErrorAction SilentlyContinue)
    if ($partitions.Count -ne 1) { return }
    $number = $partitions[0].DiskNumber
    $mounted = @($disks | Where-Object { $_.Number -eq $number })
    if ($mounted.Count -ne 1) { return }
    $disk = $mounted[0]
    if ($disk.IsReadOnly -or $disk.IsOffline -or $disk.IsClustered -or
        [string]$disk.BusType -notin $directBusTypes -or
        [string]::IsNullOrWhiteSpace($disk.UniqueId)) { return }
    if (@($disks | Where-Object { $_.UniqueId -eq $disk.UniqueId }).Count -ne 1) { return }
    $physical = @($physicalDisks | Where-Object { $_.UniqueId -eq $disk.UniqueId })
    if ($physical.Count -ne 1) { return }
    $media = [string]$physical[0].MediaType
    if ($media -in '3', 'HDD') { 'HDD' }
    if ($media -in '4', 'SSD') { 'SSD' }
}
"""

_LIST_SCRIPT = (
    _DETECT_MEDIA
    + """
$drives = @(Get-Volume |
    Where-Object { $_.DriveLetter -and [string]$_.DriveType -in 'Fixed', '3' } |
    ForEach-Object {
        [pscustomobject]@{
            letter = [string]$_.DriveLetter
            name = [string]$_.FileSystemLabel
            id = [string]$_.ObjectId
            media = Get-DriveMediaType $_
            size = $_.Size
            free = $_.SizeRemaining
        }
    })
ConvertTo-Json -InputObject $drives -Compress
"""
)


@dataclass(frozen=True)
class Drive:
    letter: str
    name: str
    object_id: str
    media: str | None
    size_bytes: int
    free_bytes: int

    @property
    def label(self) -> str:
        return f"{self.letter}: {self.name}" if self.name else f"{self.letter}:"


def _read_drive(entry: object) -> Drive | None:
    if not isinstance(entry, dict):
        return None
    letter, object_id = entry.get("letter"), entry.get("id")
    name, media = entry.get("name"), entry.get("media")
    size, free = entry.get("size"), entry.get("free")
    if not isinstance(letter, str) or not _DRIVE_LETTER.fullmatch(letter):
        return None
    if not isinstance(size, int) or not isinstance(free, int) or not 0 <= free <= size:
        return None
    identity = object_id if isinstance(object_id, str) else ""
    return Drive(
        letter,
        name if isinstance(name, str) else "",
        identity,
        media if identity and isinstance(media, str) and media in _OPERATIONS else None,
        size,
        free,
    )


def list_drives() -> list[Drive] | None:
    """Devolve None se não for possível consultar as unidades."""
    output = run_powershell(_LIST_SCRIPT)
    if output is None:
        return None
    try:
        data = json.loads(output)
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    return sorted(
        (drive for entry in data if (drive := _read_drive(entry)) is not None),
        key=lambda drive: drive.letter,
    )


def optimize_drive(drive: Drive) -> Action:
    def optimize(report: Report) -> Outcome:
        if not is_admin():
            return Outcome(0, 0, admin_required=(drive.label,))
        operation = _OPERATIONS.get(drive.media or "")
        if not operation or not _DRIVE_LETTER.fullmatch(drive.letter) or not drive.object_id:
            return Outcome(0, 0, failures=(drive.label,))

        # O identificador volta a ser comparado, pois a letra pode ter mudado de unidade.
        identity = base64.b64encode(drive.object_id.encode("utf-8")).decode("ascii")
        script = (
            _DETECT_MEDIA
            + f"""
$id = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{identity}'))
$volumes = @(Get-Volume -DriveLetter '{drive.letter}')
if ($volumes.Count -ne 1 -or $volumes[0].ObjectId -ne $id -or
    (Get-DriveMediaType $volumes[0]) -ne '{drive.media}') {{ exit 1 }}
Optimize-Volume -InputObject $volumes[0] {operation}
"""
        )
        values = {"drive": drive.label}
        try:
            succeeded = run_powershell_with_progress(
                script, report, f"performance.optimize_drives.{drive.media}.step", values
            )
        except OSError:
            succeeded = False
        if not succeeded:
            return Outcome(0, 0, failures=(drive.label,))
        return Outcome(
            0,
            0,
            rows=(Row("performance.optimize_drives.result", None, 0, values, needs_admin=True),),
        )

    return optimize
