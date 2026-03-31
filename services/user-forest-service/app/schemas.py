from typing import Optional, Any, Dict

from pydantic import BaseModel, EmailStr, Field


# === Roles ===
class RoleBase(BaseModel):
    name: str = Field(..., description="admin, agent_forestier, superviseur")


class RoleCreate(RoleBase):
    pass


class RoleRead(RoleBase):
    id: int

    class Config:
        from_attributes = True


# === Users ===
class UserBase(BaseModel):
    username: str
    email: EmailStr
    role_id: int


class UserCreate(UserBase):
    password: str
    direction_secondaire_id: Optional[int] = None
    direction_regionale_id: Optional[int] = None
    telephone: Optional[str] = None
    actif: bool = True

# Met à jour un utilisateur par id(username, email, role_id, password)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None
    password: Optional[str] = None
    direction_secondaire_id: Optional[int] = None
    telephone: Optional[str] = None
    actif: Optional[bool] = None


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: RoleRead
    direction_secondaire_id: Optional[int] = None
    direction_regionale_id: Optional[int] = None
    telephone: Optional[str] = None
    actif: bool = True

    class Config:
        from_attributes = True


# Réponse interne service-to-service (auth-service uniquement)
class UserAuthRead(BaseModel):
    id: int
    hashed_password: str
    role: str  # nom du rôle, ex: "admin"
    actif: bool

    class Config:
        from_attributes = True


# === Forests ===
class ForestBase(BaseModel):
    name: str
    description: Optional[str] = None
    # GeoJSON geometry ou Feature
    geometry: Dict[str, Any] = Field(
        ..., description="GeoJSON Polygon ou Feature avec geometry=Polygon"
    )


class ForestCreate(ForestBase):
    created_by_id: Optional[int] = None
    direction_secondaire_id: Optional[int] = None
    direction_regionale_id: Optional[int] = None
    surface_ha: Optional[float] = None
    type_foret: Optional[str] = None


class ForestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    direction_secondaire_id: Optional[int] = None
    surface_ha: Optional[float] = None
    type_foret: Optional[str] = None


class ForestRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    geometry: Dict[str, Any]
    direction_secondaire_id: Optional[int] = None
    direction_regionale_id: Optional[int] = None
    surface_ha: Optional[float] = None
    type_foret: Optional[str] = None

    class Config:
        from_attributes = True


class ForestSummaryRead(BaseModel):
    """Light payload version for list views (no geometry)."""
    id: int
    name: str
    description: Optional[str]
    direction_secondaire_id: Optional[int] = None
    surface_ha: Optional[float] = None
    type_foret: Optional[str] = None

    class Config:
        from_attributes = True


# === Parcelles ===
class ParcelleBase(BaseModel):
    forest_id: int
    name: str
    description: Optional[str] = None
    geometry: Dict[str, Any] = Field(
        ..., description="GeoJSON Polygon"
    )


class ParcelleCreate(ParcelleBase):
    created_by_id: Optional[int] = None


class ParcelleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None


class ParcelleRead(BaseModel):
    id: int
    forest_id: int
    name: str
    description: Optional[str]
    geometry: Dict[str, Any]
    surface_ha: Optional[float] = None
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class ParcelleSummaryRead(BaseModel):
    """Light payload version for list views (no geometry)."""
    id: int
    forest_id: int
    name: str
    description: Optional[str]
    surface_ha: Optional[float] = None
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True


# === Directions Régionales ===
class DirectionRegionaleBase(BaseModel):
    nom: str
    gouvernorat: str


class DirectionRegionaleCreate(DirectionRegionaleBase):
    pass


class DirectionRegionaleRead(DirectionRegionaleBase):
    id: int

    class Config:
        from_attributes = True


# === Directions Secondaires ===
class DirectionSecondaireBase(BaseModel):
    nom: str
    region_id: int


class DirectionSecondaireCreate(DirectionSecondaireBase):
    pass


class DirectionSecondaireRead(DirectionSecondaireBase):
    id: int

    class Config:
        from_attributes = True

