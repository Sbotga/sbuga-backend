from pydantic import BaseModel
from typing import Optional, List


class SekaiUserRegistrationData(BaseModel):
    userId: int
    signature: Optional[str] = None
    platform: Optional[str] = None
    deviceModel: Optional[str] = None
    operatingSystem: Optional[str] = None
    registeredAt: Optional[int] = None


class SekaiUserData(BaseModel):
    userRegistration: SekaiUserRegistrationData
    credential: Optional[str] = None
    updatedResources: Optional[dict] = None
    sessionToken: Optional[str] = None

    @property
    def user_credentials(self) -> Optional[str]:
        return self.credential or self.sessionToken


class SekaiUserAuthData(BaseModel):
    sessionToken: str
    appVersion: str
    multiPlayVersion: str
    dataVersion: str
    assetVersion: str
    removeAssetVersion: Optional[str] = None
    assetHash: Optional[str] = None
    appVersionStatus: Optional[str] = None
    isStreamingVirtualLiveForceOpenUser: Optional[bool] = None
    deviceId: Optional[str] = None
    updatedResources: Optional[dict] = None
    suiteMasterSplitPath: Optional[list] = None
    obtainedBondsRewardIds: Optional[list] = None
    cdnVersion: Optional[int] = None
    configs: Optional[List[dict]] = None
