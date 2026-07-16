from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import SquadMember


@receiver(post_save, sender=SquadMember)
def update_squad_member_count(sender, instance, created, **kwargs):
    if created:
        squad = instance.squad
        squad.member_count = squad.members.count()
        squad.save(update_fields=["member_count"])
    else:
        squad = instance.squad
        squad.member_count = squad.members.count()
        squad.save(update_fields=["member_count"])


@receiver(pre_save, sender=SquadMember)
def validate_single_captain(sender, instance, **kwargs):
    if instance.is_captain:
        SquadMember.objects.filter(squad=instance.squad, is_captain=True).exclude(
            pk=instance.pk
        ).update(is_captain=False)
    if instance.is_vice_captain:
        SquadMember.objects.filter(squad=instance.squad, is_vice_captain=True).exclude(
            pk=instance.pk
        ).update(is_vice_captain=False)
