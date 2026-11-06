# ImmersiveBattleFixes — engineering log

What each kit check and each in-game test showed, newest at the bottom. Record dead ends here so they are never
retried. Plan: [../PLAN.md](../PLAN.md); reproducible edits: [../BUILD.md](../BUILD.md). Facts that hold for any
mod go to `harness/docs/` instead (promote them).

## 2026-11-06 — repo created from the harness

## 2026-11-06 — build 1: the Granite fight (E16_MQ01_C03)
- Kit: 15 Spawn nodes, 41 Granite, all `OverrideRank` Master; Granite exist only in this level (44 actors in
  `E16_MQ01_C03_LogicLevel_WP`, 5 generic squads unused by any quest). NPC weapon shot patterns
  (`NPCWeaponAttributesPrototypes.cfg`) are the same at every rank, so rank is not an accuracy lever. Gauss NPC:
  `BaseDamage 45`, piercing 4 (inherited from the player Gauss); Grim bursts 8-16 at short range, 4-6 shots ignore
  dispersion.
- Snipers spawn the moment the elites aggro (launcher group [0]); the 15 s `Technical_Delay_Snipers` group is a no-op.
- Retail check (`pakchunk0-Windows.pak` holds merged `QuestNodePrototypes.cfg.bin` / `SpawnActorPrototypes.cfg.bin`,
  extract with `UnrealPak -Extract <dir> -Filter=*GameData/<name>.cfg.bin`, which does filter): every patched node SID
  and all 97 actors of the level exist in retail 2.1.
- Tester save before the fight: 2026-09-23 21:26 (`48B59BF6...`; Generators C01/C02 names present, C03 not started).
- Adversarial review round 1 (fresh agent): no blocking defect. Fixed: `IgnoreThreat = false` next to
  `ImmediatelyIdentifyEnemy = false` on the snipers (vanilla pairs false/true only on one boss: risk of a sniper that
  never engages and stalls `Technical_FinishGraniteStage`); `SpawnedGenericMembers` re-emitted whole (single-index
  bpatches have replaced whole lists before); no DamageMultiplier on the generic squad (squads never set it, base
  default 0, so it is not passed to members: that one Granit keeps full damage); probe added: the first Granite
  (Respawnable CC `9D8254B6`) at 0.1 to tell whether `DamageMultiplier` scales damage dealt (assumed) or taken.
  Accepted: patch placement in a level subfolder is unproven (no installed mod does it; it follows the loader rule);
  the visible elites stand idle (`Stay`, HigherThanCombat) until the trigger or a hit, and a hit starts the aggro
  without the door closing.
- Review round 2 (new agent): no defect. Decoded both retail `.cfg.bin`: all 31 patched actors and all 138 nodes of
  E16_MQ01_C03 identical to the kit, list order included. `ImmediatelyIdentifyEnemy = false` + `IgnoreThreat = false`
  on a Kill at the player has 6 vanilla precedents. Test note: the probe CC spawns at the quest start together with a
  Stormtrooper ~37 m away, and is SeamlessDespawned at `Trigger_SecondCombatZone`: the tester must let him hit up
  close before moving on; CptPrice (same type, 0.65) is the control later in the run.
