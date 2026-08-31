import enum


class RecordSignStatus9(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    CHECK_REJECTED = "CHECK_REJECTED"
    STALE = "STALE"
    CHANGE_PENDING = "CHANGE_PENDING"
    CHANGED = "CHANGED"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    OBSOLETE = "OBSOLETE"


class StreamSignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    OBSOLETE = "OBSOLETE"


class DeliverableSignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    OBSOLETE = "OBSOLETE"


class WorkspaceType(str, enum.Enum):
    FORMAL = "FORMAL"
    PERSONAL = "PERSONAL"
    TEMPORARY = "TEMPORARY"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"

