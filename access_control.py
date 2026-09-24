# access_control.py
"""
Access Control - Phân quyền người dùng
- Admin: Toàn quyền
- Leader tuần: Điều hành tuần
- Member G1: Học tập
- Guest: Chỉ xem
"""
from config import ALL_MEMBERS, ADMIN_ROLE


# ============================================================
# ROLE DEFINITIONS
# ============================================================

ROLE_ADMIN = "admin"
ROLE_LEADER = "leader"
ROLE_MEMBER = "member_g1"
ROLE_GUEST = "guest"

# Permissions theo role
PERMISSIONS = {
    ROLE_ADMIN: ["*"],
    ROLE_LEADER: [
        "quiz", "socratic", "predict", "chat",
        "plan", "plan_create", "notify", "remind",
        "missing", "week", "mode",
        "insights", "codevault", "help",
        "my_mode", "advanced_mode",
    ],
    ROLE_MEMBER: [
        "quiz", "socratic", "predict", "chat",
        "week", "mode", "insights", "codevault", "help",
        "my_mode", "advanced_mode",
    ],
    ROLE_GUEST: [
        "week", "mode", "insights", "help",
    ],
}

# Role hierarchy (cao hơn = nhiều quyền hơn)
ROLE_HIERARCHY = {
    ROLE_ADMIN: 4,
    ROLE_LEADER: 3,
    ROLE_MEMBER: 2,
    ROLE_GUEST: 1,
}


class AccessControl:
    """Quản lý phân quyền"""

    def __init__(self):
        # Leader tuần (có thể update)
        self.weekly_leader = None

    # ============================================================
    # GET ROLE
    # ============================================================

    def get_role(self, member):
        """
        Xác định role của member.

        Args:
            member: discord.Member object hoặc tên string

        Returns:
            str: role
        """
        # Nếu là discord.Member
        if hasattr(member, "roles"):
            # Check Admin role
            if any(r.name.lower() == ADMIN_ROLE.lower() for r in member.roles):
                return ROLE_ADMIN

            # Check Leader role
            if any(r.name.lower() == "leader" for r in member.roles):
                return ROLE_LEADER

            # Check nếu là member G1
            member_name = member.display_name
            if self._is_g1_member(member_name):
                return ROLE_MEMBER

            return ROLE_GUEST

        # Nếu là string (tên member)
        if isinstance(member, str):
            if self._is_g1_member(member):
                return ROLE_MEMBER
            return ROLE_GUEST

        return ROLE_GUEST

    def _is_g1_member(self, name):
        """Check xem name có phải member G1 không"""
        # Cắt hậu tố
        name_clean = name.split("-NR.")[0].strip().split("-")[0].strip()

        for m in ALL_MEMBERS:
            m_clean = m.split("-NR.")[0].strip().split("-")[0].strip()
            if m_clean.lower() == name_clean.lower():
                return True
        return False

    # ============================================================
    # CHECK PERMISSION
    # ============================================================

    def has_permission(self, member, command):
        """
        Kiểm tra member có quyền dùng command không.

        Args:
            member: discord.Member hoặc tên
            command: tên command (không có !)

        Returns:
            bool
        """
        role = self.get_role(member)
        permissions = PERMISSIONS.get(role, [])

        # Admin có tất cả
        if "*" in permissions:
            return True

        return command in permissions

    def check_role(self, member, required_role):
        """
        Kiểm tra member có role >= required_role không.

        Args:
            member: discord.Member hoặc tên
            required_role: role tối thiểu

        Returns:
            bool
        """
        user_role = self.get_role(member)
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)

        return user_level >= required_level

    # ============================================================
    # LEADER MANAGEMENT
    # ============================================================

    def set_weekly_leader(self, member):
        """Set Leader tuần (Admin)"""
        if hasattr(member, "display_name"):
            self.weekly_leader = member.display_name
        else:
            self.weekly_leader = str(member)
        print(f"[AccessControl] Weekly leader: {self.weekly_leader}")

    def get_weekly_leader(self):
        """Lấy Leader tuần"""
        return self.weekly_leader

    def is_weekly_leader(self, member):
        """Check xem member có phải Leader tuần không"""
        if not self.weekly_leader:
            return False

        if hasattr(member, "display_name"):
            member_name = member.display_name
        else:
            member_name = str(member)

        return member_name == self.weekly_leader

    # ============================================================
    # UTILS
    # ============================================================

    def get_permissions_list(self, member):
        """Lấy danh sách commands member có thể dùng"""
        role = self.get_role(member)
        return {
            "role": role,
            "permissions": PERMISSIONS.get(role, []),
        }

    def get_role_icon(self, role):
        """Icon cho role"""
        icons = {
            ROLE_ADMIN: "👑",
            ROLE_LEADER: "⭐",
            ROLE_MEMBER: "👤",
            ROLE_GUEST: "👻",
        }
        return icons.get(role, "❓")

    def get_role_name(self, role):
        """Tên hiển thị của role"""
        names = {
            ROLE_ADMIN: "Admin",
            ROLE_LEADER: "Leader tuần",
            ROLE_MEMBER: "Member G1",
            ROLE_GUEST: "Guest",
        }
        return names.get(role, "Unknown")


# ============================================================
# TEST BLOCK
# ============================================================

if __name__ == "__main__":
    ac = AccessControl()

    print("=" * 60)
    print("ACCESS CONTROL TEST")
    print("=" * 60)

    test_cases = [
        ("DatPT-NR.Admin", "scoring"),
        ("QuanAP-NR.G1", "quiz"),
        ("QuanAP-NR.G1", "scoring"),
        ("Long-NR.G1", "socratic"),
        ("Long-NR.G1", "override"),
        ("RandomUser", "week"),
        ("RandomUser", "quiz"),
    ]

    for member, command in test_cases:
        role = ac.get_role(member)
        has_perm = ac.has_permission(member, command)
        icon = ac.get_role_icon(role)
        role_name = ac.get_role_name(role)
        status = "OK" if has_perm else "DENY"
        print(f"{icon} {member:20s} | {role_name:12s} | !{command:12s} | {status}")

    print()
    print("=" * 60)
    print("LEADER TEST")
    print("=" * 60)

    ac.set_weekly_leader("QuanAP-NR.G1")
    print(f"Weekly leader: {ac.get_weekly_leader()}")
    print(f"is_weekly_leader(QuanAP): {ac.is_weekly_leader('QuanAP-NR.G1')}")
    print(f"is_weekly_leader(DatPT): {ac.is_weekly_leader('DatPT-NR.Admin')}")