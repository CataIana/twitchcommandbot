from enum import Enum

class BroadcasterType(Enum):
    partner = "partner"
    affiliate = "affiliate"
    none = ''

class UserType(Enum):
    staff = "staff"
    admin = "admin"
    global_mod = "global_mod"
    none = ""
