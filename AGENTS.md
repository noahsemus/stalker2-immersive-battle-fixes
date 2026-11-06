# ImmersiveBattleFixes — mod context for the agent

**First read `harness/AGENTS.md`**: the shared rules, tester workflow, pipeline and game knowledge for every
Stalker 2 mod. They apply here. This file holds only what is specific to this mod.

Purpose: Main-quest battles without endless waves: fewer enemies, and none spawning behind you.

Repo `noahsemus/stalker2-immersive-battle-fixes`, Zone Kit plugin `ImmersiveBattleFixes` (`/ImmersiveBattleFixes/`), asset prefix `ImmBF`. Created from the
harness on 2026-11-06.

## Current state (one line per checkpoint / release: date, what changed, what the tester confirmed in game)
- 2026-11-06: repo created; kit research done, plan written (`PLAN.md`; research in `zonekit/research/`). Waiting
  on the tester: pick `ImmersiveBattleFixes` in the editor's toolbar mod selector once (GameFeatureData), the four
  decisions in PLAN.md, which saves exist before the battles. Then build 1.
- 2026-11-06 checkpoint-granite (Noah: "granite is definitely fixed and better", "checkpoint it"; paks in
  `zonekit/builds/checkpoint-granite/`): Granite fight (E16_MQ01_C03) 41 -> 18 Granite (squad member lists trimmed,
  quest-named members kept), 1 Gauss sniper of 5, DamageMultiplier 0.65 on every kept member, elites visible, snipers
  not told where the player is; the first CC at 0.1 as a probe (not noticed: direction of DamageMultiplier still
  unproven; remove before release). Next: MCM (build 2 prepared), the Wish Granter illusion fight (E06_MQ02_C02).

## Key facts (kit research 2026-11-06; details and citations in `zonekit/research/`)
- Quest `Spawn` nodes hold no count / distance / visibility; who, where and how many is in the spawn actor
  (`SpawnActorPrototypes/WorldMap_WP/<level>/<GUID>.cfg`). Waves = respawning squads (`InfiniteRespawn`,
  `RespawnPoints[]` picked with no player check), level `EncounterNPCSpawner` / `FaustBossfightController` actors
  (contents in level data), trigger-chained gauntlets, big squads. No E06-E16 quest loops a Spawn node.
- `MinDistanceToPlayerForRespawn` exists on squads, used once in vanilla (E11_MQ01, 300).
- Psy phantoms: player PSY effects `SpawnPSYPhantoms` / `SpawnPSYNPC` (`EffectPrototypes.cfg:6694` / `6752`),
  blocked by flag effects `BlockPSYPhantomsSpawns` / `BlockPSYNPCSpawns`.
- A wave squad's `OnNPCDeathEvent` advances the quest: shrink squads, never remove them.
- Endgame zones switch the A-Life director to `EmptyGroup`; ambient spawns are not the cause there.

## Assets this mod may override
- _(none yet; see harness/docs/compatibility.md before adding any)_

## Files
- `PLAN.md` plan and test matrix · `BUILD.md` every edit asset by asset · `zonekit/README.md` engineering log
  (what each test showed, dead ends) · `zonekit/ImmersiveBattleFixes/` plugin mirror · `zonekit/tools/` mod-specific generators
  and classifier lists · `zonekit/builds/` checkpoint and release paks · `mod.json` names and pak suffixes.
- `CLAUDE.md` / `GEMINI.md` only import `harness/AGENTS.md` and this file, for tools that don't read `AGENTS.md`.

## Release (only when the tester says "cut a release")
Follow `harness/docs/pipeline.md` § Release. Nexus page: _(record the mod id here once it exists)_.
