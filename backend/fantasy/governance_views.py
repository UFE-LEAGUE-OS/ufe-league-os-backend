"""
Fantasy Governance Views
"""

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .governance_models import (
    FantasyScoringRule,
    FantasyTransferRule,
    FantasySquadRule,
    FantasyPriceStructure,
    FantasyEligibilityRule,
    FantasyCompetitionMapping,
    FantasyFeatureFlag,
)
from .serializers import (
    FantasyScoringRuleSerializer,
    FantasyTransferRuleSerializer,
    FantasySquadRuleSerializer,
    FantasyPriceStructureSerializer,
    FantasyEligibilityRuleSerializer,
    FantasyCompetitionMappingSerializer,
    FantasyFeatureFlagSerializer,
)


class FantasyScoringRuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy scoring rules.
    """
    queryset = FantasyScoringRule.objects.all()
    serializer_class = FantasyScoringRuleSerializer
    permission_classes = [permissions.IsAdminUser]


class FantasyTransferRuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy transfer rules.
    """
    queryset = FantasyTransferRule.objects.all()
    serializer_class = FantasyTransferRuleSerializer
    permission_classes = [permissions.IsAdminUser]


class FantasySquadRuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy squad rules.
    """
    queryset = FantasySquadRule.objects.all()
    serializer_class = FantasySquadRuleSerializer
    permission_classes = [permissions.IsAdminUser]


class FantasyPriceStructureViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy price structures.
    """
    queryset = FantasyPriceStructure.objects.all()
    serializer_class = FantasyPriceStructureSerializer
    permission_classes = [permissions.IsAdminUser]


class FantasyEligibilityRuleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy eligibility rules.
    """
    queryset = FantasyEligibilityRule.objects.all()
    serializer_class = FantasyEligibilityRuleSerializer
    permission_classes = [permissions.IsAdminUser]


class FantasyCompetitionMappingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy competition mappings.
    """
    queryset = FantasyCompetitionMapping.objects.all()
    serializer_class = FantasyCompetitionMappingSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        mapping = self.get_object()
        mapping.publish(request.user)
        return Response({"status": "published"})


class FantasyFeatureFlagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing fantasy feature flags.
    """
    queryset = FantasyFeatureFlag.objects.all()
    serializer_class = FantasyFeatureFlagSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        feature = self.get_object()
        feature.enable(request.user)
        return Response({"status": "enabled"})

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        feature = self.get_object()
        feature.disable()
        return Response({"status": "disabled"})