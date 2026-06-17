from accounts.models import User

from ..models import SponsorAccountMember, SponsorPackage


def get_user_sponsor_membership(user, sponsor_account):
    return SponsorAccountMember.objects.filter(
        sponsor_account=sponsor_account,
        user=user,
        is_active=True,
    ).first()


def can_manage_sponsor_members(user, sponsor_account):
    membership = get_user_sponsor_membership(user, sponsor_account)

    if membership is None:
        return False

    return membership.member_role in [
        SponsorAccountMember.MemberRole.OWNER,
        SponsorAccountMember.MemberRole.ADMIN,
    ]


def is_sponsor_hub_admin(user):
    """
    MVP permission helper for sponsor package management.

    Club admins, league admins, union admins and super admins can create
    packages. Superusers/staff are also allowed.
    """

    if user.is_staff or user.is_superuser:
        return True

    return (
        user.has_role(User.Role.CLUB_ADMIN)
        or user.has_role(User.Role.LEAGUE_ADMIN)
        or user.has_role(User.Role.UNION_ADMIN)
        or user.has_role(User.Role.SUPER_ADMIN)
    )


def can_manage_sponsor_package(user, sponsor_package):
    """
    MVP ownership permission for package management.

    Later, this should check the exact club, league, union or platform owner
    once those modules are fully linked by foreign keys.
    """

    if user.is_staff or user.is_superuser or user.has_role(User.Role.SUPER_ADMIN):
        return True

    if sponsor_package.owner_type == "CLUB":
        return user.has_role(User.Role.CLUB_ADMIN)

    if sponsor_package.owner_type == "LEAGUE":
        return user.has_role(User.Role.LEAGUE_ADMIN)

    if sponsor_package.owner_type in ["UNION", "SPORT"]:
        return user.has_role(User.Role.UNION_ADMIN)

    if sponsor_package.owner_type == "PLATFORM":
        return user.has_role(User.Role.SUPER_ADMIN)

    return False


def has_sponsor_account_access(user, sponsor_account):
    if user.is_staff or user.is_superuser or user.has_role(User.Role.SUPER_ADMIN):
        return True

    return get_user_sponsor_membership(user, sponsor_account) is not None


def can_manage_sponsor_account_finance(user, sponsor_account):
    if user.is_staff or user.is_superuser or user.has_role(User.Role.SUPER_ADMIN):
        return True

    membership = get_user_sponsor_membership(user, sponsor_account)

    if membership is None:
        return False

    return membership.member_role in [
        SponsorAccountMember.MemberRole.OWNER,
        SponsorAccountMember.MemberRole.ADMIN,
        SponsorAccountMember.MemberRole.FINANCE,
    ]


def can_access_sponsor_agreement(user, agreement):
    return has_sponsor_account_access(
        user,
        agreement.sponsor_account,
    ) or can_manage_sponsor_package(
        user,
        agreement.sponsor_package,
    )


def can_manage_sponsor_agreement(user, agreement):
    return can_manage_sponsor_account_finance(
        user,
        agreement.sponsor_account,
    ) or can_manage_sponsor_package(
        user,
        agreement.sponsor_package,
    )


def can_approve_sponsor_agreement(user, agreement):
    return can_manage_sponsor_package(user, agreement.sponsor_package)


def package_allows_sponsor_account(sponsor_package, sponsor_account):
    allowed = sponsor_package.sponsor_type_allowed

    return (
        allowed == SponsorPackage.SponsorTypeAllowed.BOTH
        or allowed == sponsor_account.sponsor_type
    )
