from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FantasyScoringRuleViewSet,
    FantasyTransferRuleViewSet,
    FantasySquadRuleViewSet,
    FantasyPriceStructureViewSet,
    FantasyEligibilityRuleViewSet,
    FantasyCompetitionMappingViewSet,
    FantasyFeatureFlagViewSet,
)

router = DefaultRouter()
router.register(
    r"scoring-rules", FantasyScoringRuleViewSet, basename="fantasy-scoring-rule"
)
router.register(
    r"transfer-rules", FantasyTransferRuleViewSet, basename="fantasy-transfer-rule"
)
router.register(r"squad-rules", FantasySquadRuleViewSet, basename="fantasy-squad-rule")
router.register(
    r"price-structures",
    FantasyPriceStructureViewSet,
    basename="fantasy-price-structure",
)
router.register(
    r"eligibility-rules",
    FantasyEligibilityRuleViewSet,
    basename="fantasy-eligibility-rule",
)
router.register(
    r"competition-mappings",
    FantasyCompetitionMappingViewSet,
    basename="fantasy-competition-mapping",
)
router.register(
    r"feature-flags", FantasyFeatureFlagViewSet, basename="fantasy-feature-flag"
)

urlpatterns = [
    path("", include(router.urls)),
]
