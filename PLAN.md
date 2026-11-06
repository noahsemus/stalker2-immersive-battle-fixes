# ImmersiveBattleFixes — plan

Main-quest battles without endless waves: fewer enemies, and none spawning behind you.

## How the game does it today (evidence: kit file:line, probe runs, tester reports)
Full research with file:line and quoted nodes: `zonekit/research/2026-11-06-endgame-battles.md` (the battles) and
`zonekit/research/2026-11-06-spawn-mechanics.md` (spawn fields, phantoms, difficulty, patching, installed mods).

- Quest `Spawn` nodes carry no count, distance or visibility: only the spawn actor GUID, `SpawnHidden`,
  `IgnoreDamageType`, `SpawnNodeExcludeType`, `Repeatable`, `StartDelay`. No E06-E16 quest loops a Spawn node.
- The waves come from four things, all data we can patch except (B):
  - **(A) Respawning squad spawn actors** (`SpawnActorPrototypes/WorldMap_WP/<level>/<GUID>.cfg`):
    `RespawnMembers`, `MaxRespawnCount`, `InfiniteRespawn`, `RespawnOnNPCCount`, `RespawnPoints[]`. The respawn
    point is picked from the list with no player-distance or sight check; `MinDistanceToPlayerForRespawn` exists
    (read by the exe) but vanilla uses it once (E11_MQ01, 3 m). This is the "they appear behind me" cause.
  - **(B) Level-placed native spawners** switched by quest signals: `EncounterNPCSpawner` (E15_MQ01 Eye of the
    Storm, E14 Kupol, E14 Richter, E06 SIRCAA yard, Wish Granter illusion) and `FaustBossfightController` (Faust
    clones; count / delays from global variables `Faust_Clone_Number`, `_Spawn_Min_Delay`, `_Spawn_Max_Delay`,
    set by quest nodes). Spawner NPC lists and points live in the level actors, not in cfg.
  - **(C) Trigger-chained gauntlets** (E16 Granite fight ~41 Granite, E15_MQ03 Red Fortress ~44 Monolith).
  - **(D) Big one-shot squads** (6-16 members).
- Psy phantoms come from the player's PSY meter (`EffectPrototypes.cfg` `SpawnPSYPhantoms` 6694 / `SpawnPSYNPC`
  6752): 10-15 m from the player in any direction (`CoreVariables.cfg:683` azimuth weights), x2 count and /2
  delay on Master. Flag effects `BlockPSYPhantomsSpawns` / `BlockPSYNPCSpawns` stop them; no quest uses them.
- Enemy gear scales with the PLAYER's rank: at Master generic Monolith can roll the Gauss rifle; Granite snipers
  always carry it. Difficulty scaling is global only.
- Installed mods: none touches an endgame quest node or spawn actor (checked against all 1,244 endgame GUIDs).

### The battles (live content only; cut content listed in the research file)
| # | Mission | Mechanism | What is wrong |
|---|---|---|---|
| 1 | SIRCAA escape after the Wish Granter: Law and Order / To the Last Drop of Blood (`E06_MQ03_C03`) | A + B | 4 squads with `InfiniteRespawn`, respawn points scattered over the yard (some near the entry), plus 2 level spawners |
| 2 | Wish Granter illusion (`E06_MQ02_C02`) | D + B | 5 Ward Recon + an encounter spawner |
| 3 | The Assault on the Duga (`E07_MQ05` / `E07_MQ06`) | A + B | `InfiniteGuard` endless until both psy lamps break; Faust clones 5 at a time every 1-2 s, then every 1 s |
| 4 | Once More unto the Breach / Happiness for Everyone (`E08_MQ04` / `E08_MQ05`) | B + D | Faust clones 4 every 2-5 s; squads of 5-7 |
| 5 | The Boundary (`E12_MQ01`) | D | 3 x 6 Stormtroopers (already gated on the player being 45-50 m away) |
| 6 | The Road to the Foundation, Enerhetyk (`E14_MQ01_C01`) | D | 6 + 6 + 6 snipers at 190 m |
| 7 | Down Below, Kupol (`E14_MQ02_C02`) | A + B | 8-man squad respawning twice at 2 points 100 m apart + 4 level spawners |
| 8 | Down Below, Korshunov boss (`E14_Bossfight_Korshunov`) | A | Phase 1 Ward pair `InfiniteRespawn`; phase 2 up to 16 extra Ward |
| 9 | Down Below, Richter boss (`E14_MQ02_C03`) | D + B | 9 Spark + a level spawner |
| 10 | Eye of the Storm (`E15_MQ01_C02`) | B | 4 level spawners, container relaunched forever |
| 11 | The Last Wish, Red Fortress (`E15_MQ03`) | C + D | ~44 Monolith; the 16-man `8_Ground` squad appears below / behind once you are up |
| 12 | Granite fight, every ending (`E16_MQ01_C03`) | C | ~41 Granite; 5 Gauss snipers 15 s after the hidden elites aggro |
| 13 | Ending finales (`E16_MQ01` / `E16_MQ02` / `E16_MQ03`) | D | squads of 3-5; garage squad spawns 22 m below its trigger |

## Approach, cheapest and least conflicting first
Everything is a cfg **patch** (bpatch of single spawn actors and single quest nodes); no asset override, no
whole-file cfg. Per `harness/docs/cfg-reference.md`.

| Layer | Change | Ships as | Conflicts |
|---|---|---|---|
| 1 | Respawning squads (A): `InfiniteRespawn = false`, lower `MaxRespawnCount`, `MinDistanceToPlayerForRespawn` (~40 m), drop the respawn points that sit on the player's path | `SpawnActorPrototypes/WorldMap_WP/<level>/<GUID>/<GUID>_patch_ImmersiveBattleFixes.cfg` | none installed |
| 2 | Faust clones (B): patch the `SetGlobalVariable_Faust_Clone_*` nodes (fewer, slower) | `QuestNodePrototypes/<Quest>/<Quest>_patch_ImmersiveBattleFixes.cfg` | none installed |
| 3 | Big squads (C, D): shorter member lists, fewer snipers; move or re-trigger squads that spawn behind (Red Fortress `8_Ground`, E16 garage) | spawn actor patches (+ trigger / position fields) | none installed |
| 4 | Level spawners (B): first read their NPC lists and points in the editor (editor Python on the logic levels), then throttle by re-gating their enable signals / the E15_MQ01 relaunch | quest node patches | none installed |
| 5 | Psy phantoms during these battles (if the tester wants it): `SetCharacterEffect` on the player with the block flags at battle start, removed at the end | quest node patches (added nodes) | none installed |

Existing saves: a squad that has not spawned yet uses the patched data, so test from a save made before each
fight. Forcing a refresh of an already-spawned quest squad (`NodePrototypeAppliedMods`) can break its death event
and stall the mission: not used unless a test shows we need it.

Never remove a squad outright: its `OnNPCDeathEvent` drives the next step. Shrink it instead.

## Open questions and how each gets answered
| Question | Answered by |
|---|---|
| Which battles, how much fewer enemies, phantoms, Gauss | tester (decisions below) |
| Does `MinDistanceToPlayerForRespawn` hold on every squad, and in which units | build 1, test at the SIRCAA yard or Korshunov |
| Encounter spawner NPC lists, counts and points | editor Python on the logic levels (agent), editor look if Python can't see them |
| Which way the PSY azimuth 0 deg points | only if the tester wants phantoms moved instead of blocked |
| Saves before each battle | tester's saves; otherwise a save pack |

## Decisions (tester)
- [ ] Scope: all 13 battles above, or a subset.
- [ ] How many fewer: proposed respawning squads finite (one refill at most), big squads about halved, Faust
      clones 5 -> 2 every 5-8 s.
- [ ] Psy phantoms during these battles: block / leave vanilla.
- [ ] Gauss rifles on generic Monolith at Master: leave / swap in these battles only.

## Test matrix (all must pass before a release)
| # | Setup | Steps | Expected |
|---|---|---|---|
| 1 | save before each battle in scope | play the fight through | fewer enemies, none appearing behind or next to you, the mission advances |
| 2 | save in the middle of a battle | load, finish | mission still advances (no stuck objective) |
| 3 | every ending branch (Ward, Spark, Strelok, Skif) | Generators -> ending | ending plays |
| 4 | with our other mods and Real A-Life installed | any battle | as 1 |
| 5 | death and reload during a battle | | as 1 |
