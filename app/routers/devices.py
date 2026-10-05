from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.deps import CurrentUser, Db, get_owned
from app.models import Device, utcnow
from app.schemas import DeviceIn, DeviceOut, DeviceSystemMetrics

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
def list_devices(db: Db, user: CurrentUser):
    return db.scalars(
        select(Device).where(Device.user_id == user.id).order_by(Device.created_at.desc())
    ).all()


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def pair_device(body: DeviceIn, response: Response, db: Db, user: CurrentUser):
    """Registers a paired device. Pairing the same MAC address again updates it."""
    mac_address = body.mac_address.strip().upper()
    device = db.scalar(
        select(Device).where(Device.user_id == user.id, Device.mac_address == mac_address)
    )
    if device is None:
        device = Device(user_id=user.id, mac_address=mac_address)
        db.add(device)
    else:
        response.status_code = status.HTTP_200_OK
    device.name = body.name
    device.device_type = body.device_type
    device.manufacturer = body.manufacturer
    device.last_seen_at = utcnow()
    db.commit()
    return device


@router.put("/{device_id}/metrics", response_model=DeviceOut)
def report_metrics(device_id: str, body: DeviceSystemMetrics, db: Db, user: CurrentUser):
    device = get_owned(db, Device, device_id, user)
    device.metrics = body.model_dump(mode="json")
    device.last_seen_at = utcnow()
    db.commit()
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpair_device(device_id: str, db: Db, user: CurrentUser):
    db.delete(get_owned(db, Device, device_id, user))
    db.commit()
