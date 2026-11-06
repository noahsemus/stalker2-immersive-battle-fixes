# Quest battle fixes: research on the late-game / ending battles (2026-11-06)

Read-only research of the Zone Kit GameData (game 2.x cfgs). Paths below are relative to
`G:/Epic Games/STALKER2ZoneKit/Stalker2/Content/GameLite/GameData/`:
`QN/` = `QuestNodePrototypes/`, `SAP/` = `SpawnActorPrototypes/WorldMap_WP/`. Line numbers are the line where the
node's `<SID> : struct.begin` starts. English names come from the retail `Game.locres` (`en`), dumped to
`scratchpad/en.json` (keys `sid_journal_<Quest>_Name`, `sid_journal_stage_<Stage>`).
Helper scripts (parser, graph dumps) are in `scratchpad/scripts/`; raw outputs in `scratchpad/spawns_all.txt`,
`spawns_combat*.txt`, `trigdist.txt`, `dump_*.txt`.

## 0. Headline findings

1. **Quest nodes almost never loop.** A strongly-connected-component search over the launcher graph of every
   E06-E16 quest found **no Spawn node in any cycle**, and no live `Repeatable = true` Spawn node. The "endless
   waves" come from four other mechanisms, three of which are NOT quest-node loops:
   - **(A) Respawning squad spawn actors**: `SpawnType = ESpawnType::Squad` with `RespawnMembers = true`,
     `MaxRespawnCount`, `InfiniteRespawn`, `RespawnOnNPCCount`, `RespawnPoints[]` (random respawn among several
     points). Used by: SIRCAA escape after the Wish Granter (E06_MQ03_C03, 4 squads, **InfiniteRespawn**), Duga
     assault (E07_MQ05/06 "InfiniteGuard", **InfiniteRespawn**), Korshunov boss fight (E14, 3 squads, one
     **InfiniteRespawn**), Kupol/Olimpia (E14_MQ02_C02).
   - **(B) Level-placed native spawner actors** driven by quest signals: `/Script/Stalker2.EncounterNPCSpawner`
     (`enable` / `disable` / `despawn`, signal `all_npc_killed_sender`) and `/Script/Stalker2.FaustBossfightController`
     (Faust clones / psy phantoms, `set_clone_spawn_enabled`, tuned by global variables `Faust_Clone_Number`,
     `Faust_Clone_Spawn_Min_Delay`, `Faust_Clone_Spawn_Max_Delay`). **Their NPC lists, counts and spawn points
     are NOT in any cfg** (not in SpawnActorPrototypes, not referenced by NPCSpawnerPrototypes) - they live in the
     level actors (World Partition) and must be inspected in the editor. Used by: E15_MQ01 "Eye of the Storm"
     (4 spawners, container relaunched in a loop), E14_MQ02 Kupol (4 spawners), E14_MQ02_C03 Richter fight
     (Spark spawner), E06_MQ03_C03 (Varta/Monolith "AfterSignal" spawners), E06_MQ02_C02 (Wish Granter
     "Illusion" Varta spawner), E07_MQ05/06 + E08_MQ04/05 (Faust clones every 1-2 s).
   - **(C) Long trigger-chained gauntlets**: 10-16 squads spawned one after another by trigger volumes the player
     walks through (Granite fight E16_MQ01_C03 = ~41 Granite; Red Fortress E15_MQ03 = ~44 Monolith, incl. one
     16-man squad).
   - **(D) Big one-shot squads** (6-16 members) spawned at a stage start (E12_MQ01 3 x 6 Stormtroopers, E14_MQ01
     Enerhetyk 6 snipers + 12, E15_MQ03 16-man "8_Ground").
2. **No visibility / "behind the player" logic exists on Spawn nodes.** Spawn node fields are only `SID, QuestSID,
   NodeType, Launchers, TargetQuestGuid, IgnoreDamageType, SpawnHidden, SpawnNodeExcludeType, Repeatable,
   StartDelay, NodePrototypeVersion, BrokenGameDataFilter`. Placement is fixed by the spawn actor position
   (+ `SpawnInRadius` scatter) and, for respawning squads, a random pick among `RespawnPoints`. The only
   player-relative spawn guards in the data are: quest conditions `DistanceToPoint` (E12_MQ01 picks the Monolith
   flank the player is >=45-50 m from; E14_MQ01_C01 gates squads on distance) and the squad field
   `MinDistanceToPlayerForRespawn` (exists, used exactly once in the whole game: E11_MQ01 snorks, 300 = 3 m).
   `LookAtAngle` exists as a condition but never gates a combat spawn.
3. **A-Life director is switched OFF in the endgame zones** (`ALifeDirectorZoneSwitch` with
   `OverrideScenarioGroupSID = EmptyGroup` in E15_MQ01 L1690, E15_MQ02 L7479/L7499, E16_MQ01 L7987, E16_MQ02 L10198;
   `rootgraph` also has `AlifeDirectorDisable`), so random ambient spawns are not the cause there.
4. **Enemy gear scales with the PLAYER's rank** (item generators `PlayerRank = Master`): by the endgame Monolith
   Recon/Stormtrooper/Sniper can roll the **Gauss rifle** (`GunGauss_SP`), Granite snipers carry the Gauss rifle at
   every rank, Granite stormtroopers `Lavina/Grim/Kharod`, close-combat `SPSA/D12/Ram2` shotguns. Granite have
   170 HP (`ObjPrototypes/Granit.cfg:1`), a shield ability and Strelok-style dash evasion.
5. Several "infinite" structures in the data are **dead/cut content** (not launched or placeholder missing):
   `E07_MQ04` + `E07_DugaAssault(_C01)` (rootgraph container has no launcher; 36 + 18 chained "MoreTroops"
   spawns), `E14_MQ02_C04/_C05` ("OlimpiaMonolithInfiniteSquad" loops, placeholder GUIDs absent), Korshunov
   `Container_CombatVarta1` (no launcher). Don't spend effort there.

## 1. Main quests near the end and the ending branches

`QN/rootgraph.cfg` containers and their launchers (dump: `scratchpad/scripts/dump.py rootgraph.cfg`).
`MainlineBranch` global variable (`GlobalVariablePrototypes.cfg:69`): 0 none, 1 Ward (Varta), 2 Spark (Iskra),
3 Strelok, 4 Skif alone.

| Code | English name | Branch / launched by (rootgraph line) |
|---|---|---|
| E06_MQ02 | Wishful Thinking ("Make a wish by the Monolith" = the Wish Granter at SIRCAA) | after E06_MQ01 (L1391). Outputs `End_Illigals` / `End_Varta` |
| E06_MQ03 | Law and Order (escape SIRCAA ruins, Ward side) | E06_MQ02 End_Varta (L1414) |
| E06_MQ04 | To the Last Drop of Blood (escape SIRCAA, Noontide/"illegals" side) | E06_MQ02 End_Illigals (L1436). Shares containers E06_MQ03_C01..C04 |
| E07_MQ05 | The Assault on the Duga (Ward route) | E07_MQ01 End_Varta (L2143) |
| E07_MQ06 | The Assault on the Duga (Scar route) | E07_MQ03 (L2165) |
| E07_MQ04 (+E07_DugaAssault) | (no journal name) | **never launched** (L1610 `Launchers =` empty) - cut content |
| E08_MQ04 | Once More unto the Breach (Ward) | E08_MQ03 End_Ward (L1564) |
| E08_MQ05 | Happiness for Everyone (Spark) | E08_MQ03 End_Spark (L1622) |
| E11_MQ04 | Escape from the Cage | E11_MQ03 End_SparkANDStrider (L1887) |
| E12_MQ01 | The Boundary | E11_MQ03 End_Ward / E11_MQ04 (L1910) |
| E14_MQ01 | The Road to the Foundation | E12_MQ01 (L1963) |
| E14_MQ02 | Down Below (Foundation; Korshunov or Richter boss) | E14_MQ01 (L1986). Outputs `End_Ward` / `End_Spark` / `End_Strider` |
| E15_MQ01 (E15_MQ01_P) | Eye of the Storm (Generators, emission shelters) | **Ward** (L2010) |
| E15_MQ02 | Through the valley of the shadow of death | **Spark** (L2032) |
| E15_MQ03 | The Last Wish (Kaimanov, Red Fortress, Strelok choice) | **Strider** (L2054) |
| E16_MQ01 | The Last Step | **Ward ending** (L2076) |
| E16_MQ02 | The Eternal Shining | **Spark (Scar) ending** (L2098) |
| E16_MQ03 | Let No One Leave Unsatisfied | **Strelok / Skif endings** (L2120; outputs `End_Strelok`, `End_Skif`) |

The Generators interior content shared by every ending runs in `E16_MQ01_P` (contained by `Generators_L`,
`QN/Generators_L.cfg:37`), which launches `E16_MQ01_C01` (first Monolith combat), `E16_MQ01_C02` (Granite before
the lift) and `E16_MQ01_C03` (the Granite fight) from player triggers (`E16_MQ01_P.cfg` L554/L600/L646). Final
cutscenes: `C_E16_MQ03_Final_TheWard/TheSpark/Strelok/Skif_Cutscene.cfg`. The Wish Granter "wishes" themselves
(`E06_MQ02_C01.cfg`: Power/Destroy/Control/Immortal/Money "Phantom" branches) are `PlayVideo` endings, not fights.

## 2. Battles, one by one

Member counts = `SpawnedGenericMembers[].SpawnedSquadMembersCount` + one per `SquadMembersQuestSIDs[]` GUID
(each resolved to its own Obj spawn actor). Distances = 2D distance from the centre of the trigger volume that
launches the spawn to the spawn actor (`scratchpad/trigdist.txt`).

### 2.1 SIRCAA escape after the Wish Granter - E06_MQ03 "Law and Order" / E06_MQ04 "To the Last Drop of Blood"
`QN/E06_MQ03_C03.cfg` (contained by both E06_MQ03 L47 and E06_MQ04 L619). Ward vs Monolith "SimulateBattle" in
the SIRCAA yard/garden; if the player helped Noontide, `ChangeRelationships_VartaEnemy` (L211) makes the Ward
hostile too, so both sides shoot the player.
- One-shot: `Spawn_VartaYard` L44 (6 Varta Recon) + `Spawn_MonolithYard` L65 (5 Monolith Recon) on trigger
  `CorruptedInfostand` (spawn 50 m away); `Spawn_VartaYard2` L245 (3) + `Spawn_MonolithYard2` L266 (1).
- **Infinite respawning squads** (mechanism A):
  - `Spawn_InfiniteVarta3` L2117 -> `SAP/E06_MQ03_LogicLevel_WP/09C162B8463AE62B93FB9991206B7ECE.cfg` (2 Varta
    CloseCombat + 1 Recon) and `Spawn_InfiniteMonolith` L2138 -> `B6F62575412FD8BF105CE582FF0FE8D5.cfg`
    (3 Monolith CloseCombat), both from `Technical_InfiniteSpawn` L2239 (journal stage `E06_MQ03_TakeInfo` /
    `E06_MQ04_Data` finished).
  - `Spawn_InfitineVarta` L2591 -> `FAAFDAB146B95C7C1C263E82E4D4BC47.cfg` (1 CC + 2 Recon) and
    `Spawn_InfiniteMonolith_1` L2653 -> `E9738C264F6D46B75AFA71A788994F9D.cfg` (3 CloseCombat), from
    `OnTriggerEnterEvent_1` (trigger 9B0E4A47..., spawn ~120 m away) and re-launched by
    `OnNPCDeathEvent_BP_Squad_GardenMonolith_1` gated by `JournalState E06_MQ03 Active`.
  - All four: `MaxRespawnCount = 3`, `InfiniteRespawn = true`, `RespawnOnNPCCount = 2`, `SpawnInRadius = 100`,
    4-5 `RespawnPoints` spread over ~80 x 130 m of the yard, e.g. `09C162B8...cfg`:
    ```
    RespawnMembers = true
    MaxRespawnCount = 3
    InfiniteRespawn = true
    RespawnOnNPCCount = 2
    RespawnPoints : struct.begin
       [0] = X=656680.364 Y=457851.478 Z=2461.679
       [1] = X=663924.873 Y=454073.433 Z=2457.031
       [2] = X=660756.221 Y=463633.435 Z=2451.287
       [3] = X=664240.396 Y=462590.443 Z=2456.074
       [4] = X=656426.632 Y=467178.549 Z=1603.762
    ```
    Respawn points are far apart and some lie within ~45 m of the entry trigger, so members reappear at random
    points around (and behind) the player. Endless until the container ends (`SpawnNodeExcludeType`
    SeamlessDespawn/KillSpawnedObj on exclusion).
- Plus level spawners (mechanism B): `SendSignal_VartaAfterSignalEnableSpawnReceiver` L1063 (receiver
  704A8AF7...) and `SendSignal_MonolithAfterSignal2EnableSpawnReceiver` L1090 (AADCD377...), 3 s after the
  helicopter scene. Contents unknown from cfg.
- E06_MQ03_C01 (tunnels): one-shot squads of 4+4+2 in the "BigRoom" re-spawned once by `Technical_NewSpawn`
  (L6252/L6273/L6396), spawned 1-9 m from the trigger the player stands in.
- Wish Granter illusion: `QN/E06_MQ02_C02.cfg` `Spawn_AgressiveVarta` L25 (5 Varta Recon,
  `SAP/E06_MQ02_LogicLevel_WP/EEE2DEAC40C7F030E43F8B8B59484FBA.cfg`) + `SendSignalIllusionVartaEnableSpawnReceiver`
  L173 (an encounter spawner); `SAP/E06_MQ02_LogicLevel_WP` also holds 5 Varta Recon with
  `PsyNPCType = EPsyNPCType::PsyNPC`.

### 2.2 The Assault on the Duga - E07_MQ05 (Ward) / E07_MQ06 (Scar)
`QN/E07_MQ05.cfg`:
- Barricades: `Monolith_SquadOne` L149 (4 Monolith Stormtroopers), `SquadTwo` L283 (2 Snipers + 1 Storm),
  `Avantgarde` L2617 (4 Storm), from `Technical_FightForBarricades` bridges.
- KPP: `Monolith_SquadThree` L651 (3 Storm + 2 CC, from `Technical_FightForKPP` L459 = psy lamps off),
  `HoldKPP` L793 (2 Recon + 1 CC), `HoldKPP_2` L9050 (same), `Snipers` L832 (3 Snipers).
- **`Monolith_InfiniteGuard`** L3408 -> `SAP/E07_MQ05_LogicLevel_WP/6C86405D4C8FB51373670BA1367FF71D.cfg`
  (1 Recon + 1 Storm, `MaxRespawnCount = 5`, **`InfiniteRespawn = true`**, `RespawnOnNPCCount = 2`, one respawn
  point at the spawn point). Launched by `Technical_LampsOn` (L6037: trigger `Activate_PsyLamps` 53 m away, or a
  barricade squad dying), **excluded by `Technical_LampsOff`** (L401: both psy lamps broken). So it is endless
  until the player breaks the lamps. E07_MQ06 re-uses the same actor at L3333 (from `E07_MQ06_Start`, excluded
  when the player sleeps, `excl=ForceDespawn`).
- Faust clones (mechanism B): `SendSignal_FaustClone_StartSpawning` L6316 (from `Technical_StartKPPDefence`
  L5998), stopped by `SendSignal_FaustClone_StopSpawning` L6334. Tuned live:
  `SetGlobalVariable_Faust_Clone_Number` L6137 = **5**, `..._Spawn_Min_Delay` L8923 = **1**, `..._Max_Delay`
  L8943 = **2** s, later 3/5 s (L8992/L9012), then **1/1 s** after the Duga activates (L9132/L9152).
  Defaults in `GlobalVariablePrototypes.cfg`: Number 3, Min 5, Max 8. E07_MQ06 sets Number = 5 at L3851,
  start/stop signals L3871/L3890. (Clones = `FaustMonolith_CloseCombat/Stormtrooper`,
  `ObjPrototypes/GeneralNPCObjPrototypes.cfg:2845`, `BP_AI_Faust_Clone`.)
- `SpawnObjectNPCMonster_FaustClones` L1027 (5 Monolith Recon, respawn max 5) has no launcher: unused.
- E07_MQ06: Monolith_Main L838 (2 CC + 3 Recon, trigger 31 m away), Underground L390 (2 Recon + 2 Storm, 62 m),
  FaustFantoms L1104 (2 Storm + 1 CC).

### 2.3 Once More unto the Breach (E08_MQ04, Ward) / Happiness for Everyone (E08_MQ05, Spark)
Big but finite trigger-chained squads; Faust clone controllers (B):
- E08_MQ04: Monolith_KPP L594 (6 Storm + 1 Sniper), Machinegunners L2043 (6), RoadToLiterD L2117 (5, 86 m from
  trigger), LiterD_Guards L2138 (5), LiterD_Inside L2499 (6, 24 m), Techtunnel1/2 L2595/L2818 (3/5);
  E08_MQ04_C01 Commcenter (4+2+3+4+2). Faust controllers `BP_FaustBossfightController4/5` in `E08_MQ04_C02/C03`
  (Number 4, delay 2-5 s; `E08_MQ04_C02.cfg` L43/L502-L540).
- E08_MQ05 "Fight off the Monolithians": MonoLightAttack L1875 (1 Recon + 6 Storm), MonoAssaultStation_1/_2
  L1669/L8787 (5 / 7) with "_Respawn" copies L21055/L21115 for old saves, KPPDefenders L8317/L8700 (7 / 6),
  TransformerGuards L8742 (+ extra L17666). Faust controllers Parking/Transformer in `E08_MQ05_C01/C02`
  (Number 4, Min 2 s, Max 5 s; `E08_MQ05_C01.cfg` L502-L540), container `Container_PhantomZoneTransformer` is
  re-launched by repeatable `Technical_49` L19765.

### 2.4 The Boundary - E12_MQ01 ("Fight off the Monolith assault" at Yanov)
`QN/E12_MQ01.cfg`: `SpawnMonolith_1` L338 (6 Stormtroopers, `SpawnInRadius` 598) from `Trigger_Player_ONYanovExit`
(trigger L3819, squad 73 m away); `SpawnMonolith_2` L4280 (6 Storm, right flank) and `SpawnMonolith_3` L4319
(6 Storm, left flank), launched through `If_DistanceToRight` L14331 / `If_DistanceToLeft` L14374:
```
ConditionType = EQuestConditionType::DistanceToPoint
ConditionComparance = EConditionComparance::GreaterOrEqual
NumericValue = 4500.0          (left: 5000.0)
```
i.e. a flank spawns only if the player is at least 45/50 m from its spawn point - the only "don't spawn on top
of the player" logic in the main quest. 18 Stormtroopers total; ends when all three squads die
(`Technical_YanovMonolithKilled` L4367 -> `FightMonolith_Finish` L799). Limansk part: `Monolith_1Squad` L4095
(1 Sniper + 6 Storm + 1 CC) + 2 single snipers.

### 2.5 The Road to the Foundation - E14_MQ01 ("Fight off the Monolith attack on the Enerhetyk")
`QN/E14_MQ01_C01.cfg`: attackers `Spawn_DownstairsMonolithSquad` L85 (4 Storm + 2 Snipers), `Spawn_UpstairsMonolith_2`
L1149 (5 Storm + 1 CC), `Spawn_Monolith_Snipers` L764 (**6 Snipers**, `SAP/E14_MQ01_LogicLevel_WP/7465D86B...`,
at (235625,175025,1432), ~190 m north of the palace = long-range fire); defenders (Corpus) 3 + 5. Each spawn is
gated by a `DistanceToPoint ... LessOrEqual` condition (player close to the palace). Finite: 18 Monolith; ends at
`SetJournal_SaveEnergetic_Fin`. Also E14_MQ01_C04 L141 (6 Monolith).

### 2.6 Down Below - E14_MQ02 (Foundation; Kupol/Olimpia; Korshunov or Richter boss)
- **Kupol (Olimpia)**, `QN/E14_MQ02_C02.cfg`: `MonolithEnemies_Olimpia` L4293 ->
  `SAP/E14_MQ02_LogicLevel_WP/BB79A282488ED4F6B3B07D9241F4FE87.cfg` (4 CC + 3 Recon + 1 Storm = 8,
  `RespawnMembers = true`, `MaxRespawnCount = 2`, `InfiniteRespawn = false`, `RespawnOnNPCCount = 2`, 2 respawn
  points ~100 m apart: (229435,126798,-3147) and (233884,135911,-3765)) from triggers `AttackKupol`/`DownStairs`
  (59 m away); excluded on `LeftKupol`. Plus 4 EncounterNPCSpawners (B): `SnipersKupol1stGroup` L5245,
  `KupolAfterFirstSquadDeath` L5350 (launched from the Olimpia squad's Spawn output), `KupolLeftPart` L5635,
  `Kupol_Monolith_LastWave_RightPartTopZone` L5861; and one-shot squads near the cabin (1, 1, 3, 3, 2 members,
  16-37 m from their triggers), `MonolithLastWave` L3098 (2).
- **Polissya hotel** `QN/E14_MQ02_C01.cfg`: 13 zombies + controller L2924/L2505 (52/75 m), Spark/Ward groups 4+4
  from three alternative triggers (BehindHotel / SideEntrance / FrontEntrance, L5571/L6055) - the squad spawns
  ~50 m from whichever entrance the player uses.
- **Korshunov boss** (`E14_Bossfight_Korshunov`, Spark/Strider branches), `QN/E14_Bossfight_Korshunov.cfg`:
  - Phase 1: `..._AllyVartaEnemy` L2223 -> `SAP/E14_Bossfight_Korshunov_LogicLevel_WP/2DE801844AAD3B10E247BC82E80C8DFB.cfg`
    (1 Varta Recon + 1 Storm, `MaxRespawnCount = 3`, **`InfiniteRespawn = true`**, 2 respawn points), 12 s after
    combat starts (`Technical_2` L3251), excluded at Phase1_Finished (`Technical_3` L2366).
  - Phase 2: `Varta_Sniper` L2965 (`C4A60205...cfg`, 2 snipers) + `Varta_Storm` L3013 (`3570516E...cfg`, 2 Storm),
    each `MaxRespawnCount = 3`, `RespawnOnNPCCount = 1`; excluded by `BridgeEvent_2` (C02 `Technical_DespawnWard`).
    (Up to 2+2 x 4 = 16 extra Ward over phase 2, on top of the exoskeleton boss.)
- **Richter boss** (Ward branch), `QN/E14_MQ02_C03.cfg`: `Spawn_SparkBossfight1` L61 (3 Recon + 2 Storm + 4 CC = 9)
  + `BP_EncounterNPCSpawner_SparkSpawner` L712 / L1807 (B).

### 2.7 Eye of the Storm - E15_MQ01 (Ward route, Generators during emissions)
`QN/E15_MQ01.cfg` `Container_2` L2190 -> `E15_MQ01_C02`, **re-launched forever** by repeatable `Technical_13`
L2221 (`StartDelay = 1.0`) each time C02 ends. `QN/E15_MQ01_C02.cfg`: on Start, `Technical_3` enables 4
EncounterNPCSpawners (L146/L164/L182/L200 `BP_EncounterNPCSpawner_E15_MQ01_1..4 EnableSpawnReceiver`); entering
the Beta/Gamma shelter triggers disables them (L397-L451); exiting Alpha/Beta/Gamma ends the container (L469)
-> relaunch -> spawners on again. NPC type/count is defined on the level actors only. `Phantom*` technical nodes
(L2017-L2108) sit on the emission chain. Spawn counts in cfg: only 2 named NPCs - the enemies here are all from
the level spawners (needs an editor look).

### 2.8 The Last Wish - E15_MQ03 (Strider route; Red Fortress)
`QN/E15_MQ03.cfg`, all launched by `BridgeEvent_16` L2998 (stage `get_to_red_castle` started), except squad 3:
| Node (line) | Members | Position (x,y,z) |
|---|---|---|
| `SpawnNPC_Monolith_Squad_1` L2973 | 1 Storm, 2 Recon, 1 Sniper | (473518,337819,563) |
| `_Squad_2` L3252 | 1 CC, 2 Snipers, 1 Recon | (480952,342538,1101) |
| `_Squad_3` L3273 (trigger `OnTriggerEnterEvent`, 29 m) | 2 CC, 1 Sniper, 1 Storm | (483848,344006,2650) |
| `_Squad_4` L3294 | Storm, Sniper, CC, Recon | (487154,343546,3383) |
| `_Squad_5` L3315 | 4 Storm | (487123,329673,3123) |
| `_Squad_6` L3336 | 2 Storm, Sniper, CC | (492030,329085,3147) |
| `_Squad_7` L3357 | Storm, 2 Recon, CC | (494854,326719,3987) |
| `SpawnObjectNPCMonster_BP_SquadMonolith_8_Ground` L3849 (trigger `OnTriggerEnterEvent_1`, spawn 123 m from it, 26 m lower) | **3 Snipers, 8 Storm, 4 Recon, 1 CC = 16** | (492402,332076,502) |
About 44 Monolith in one climb; squads are pre-placed at every height of the fortress (z 5.6 m -> 40 m) and the
16-man "Ground" squad appears below/behind the player once they are up the structure. Finite. Stage
`kill_monolith_first_wave` finishes on `OnNPCDeathEvent_MonolithSquad` (L3231). SetAIBehavior "Stay" with
`ContextualActionRange` 1500-2500 holds them in place (L5023-L5310).

### 2.9 The Last Step / Eternal Shining / Let No One Leave Unsatisfied - E16 endings (Generators, Lab X-7)
Shared Generators content `E16_MQ01_P` -> C01/C02/C03 (every ending):
- `QN/E16_MQ01_C01.cfg`: MonolithSquad1 L36 (4), Squad4 L157 (2, 35 m), Monolith1/2/3 (3/2/3), sniper L1533
  (3 m from trigger).
- `QN/E16_MQ01_C02.cfg`: Monolith L45 (4), Granite before the lift L308 (4, 18 m), extra CC L952.
- **Granite fight** `QN/E16_MQ01_C03.cfg` (launched by `Trigger_Player_GraniteFight` or the button
  `OnInteractEvent_ButtonStartSpawn`, `E16_MQ01_P.cfg` L646), a sequential gauntlet:

  | Node (line) | Members | Trigger -> distance |
  |---|---|---|
  | `Granit_Respawnable` L33 / `_1` L208 (Start) | 1 CC / 2 Sniper + 2 Storm | none (no respawn fields despite the name) |
  | `Granit_SqThree` L445 + `SqOne2` L1987 | 2 / 3 | `Trigger_Spawn_Granit_SqThree` 48 / 59 m |
  | `SqFour` L530 | 2 | `SecondCombatZone` 19 m (despawns Sq1/Sq2) |
  | `SqFive` L737 | 2 | `Spawn_SqFive` 10 m |
  | `SqSix` L825 | 3 | `Spawn_SqSix` 29 m |
  | `SqSeven` L1092 | 2 | `Spawn_Granit_SqSeven` 20 m (despawns 4-6) |
  | `SqNine` L1180 | 3 | `Spawn_Granit_Panopticon` 12 m |
  | `SqTen` L1201 | 6 (4 Storm + 2 Sniper) | `Spawn_Granit_SqTen` 18 m |
  | `SqEleven` L1451 | 2 | signal (sparks effect) |
  | `CptPrice` L2115 | 1 | 15 m |
  | `Granite_Elites` L1764 | 2 CC + 2 Storm, **spawned hidden** (`ToggleNPCHidden ForceHide` L3261, unhidden on aggro L3280) | 18 m |
  | `Snipers` L2259 | **5 Granit_Sniper (Gauss)** | 15 s after elites aggro (`Technical_Delay_Snipers` L2241), 10 m |
  | `FinalSquad` L2414 | 1 | 30 s later (`Technical_Delay2` L2396) or elites dead |

  ~41 Granite, finite; ends when elites + snipers + last squad die (`Technical_FinishGraniteStage` L2997).
  Earlier squads are force-despawned as the player advances (`Trigger_Despawn_All` L1636).
- `QN/E16_MQ02.cfg` (Spark ending): InitialMonolith L70 (5, 57 m), MonolithInTheControlRoom L124 (5 Recon, 36 m),
  MonolithNearEntrance L3460 (3, 28 m).
- `QN/E16_MQ03.cfg` (Strelok/Skif): MonolithInGarage L3817 (3, 22 m away and 22 m below the elevator trigger).
- Bosses: `E16_Bossfight_Scar.cfg` (ScarBoss L63), `E16_Bossfight_Strelok.cfg` (StrelokMutant L27, driven by
  `BP_StrelokBossfightController`). Psy phantoms in these fights come from NPC abilities
  (`Human_PhantomAttack`, `SpawnPhantomParams` -> `BP_AI_PsyPhantomHuman`,
  `ObjPrototypes/GeneralNPCObjPrototypes.cfg:34-62`), not from quest spawns.

### 2.10 Dead / cut content (ignore)
- `QN/E07_DugaAssault.cfg` `Spawn_EndlessMonoSquad` L2929 / `Spawn_EndlessVartaSquad` L3008 ("MoreTroops") and
  `QN/E07_DugaAssault_C01.cfg` 36 chained Monolith + 18 Varta single spawns (each MonoMore_N launches MonoMore_N+4):
  only reachable from `E07_MQ04`, whose rootgraph container has no launcher; `A98F74DD...` placeholder missing.
- `QN/E14_MQ02_C04.cfg` (`OlimpiaMonolithInfiniteSquad`, Repeatable Spawn re-launched by its own
  `OnNPCDeathEvent` - the only true quest-node respawn loop in the game) and `E14_MQ02_C05.cfg` (two "Infinite
  sniper" spawns): not contained anywhere, placeholders `5B9B35D7...`, `A59E9D6B...`, `8657DB80...` do not exist.
- `E14_Bossfight_Korshunov_C03` (`EncounterNPCSpawner_WardTwo_SecondWave`): `Container_CombatVarta1` L258 has no
  launcher.
- `SAP/E07_MQ05_LogicLevel_WP/DCB733E1...cfg`, `EE52280F...cfg` (respawning Monolith squads): referenced by no node.

## 3. Placement relative to the player; every position/visibility-related field

### Spawn node (quest) fields - complete list seen on 300+ Spawn nodes
`SID, NodePrototypeVersion, QuestSID, NodeType, Launchers, TargetQuestGuid, IgnoreDamageType
(None/Unfocusable), SpawnHidden (always false), SpawnNodeExcludeType (SeamlessDespawn / KillSpawnedObj /
ForceDespawn), Repeatable, StartDelay, BrokenGameDataFilter`. Nothing about visibility, distance, or choosing
among placeholders. Hiding is done with a separate `ToggleNPCHidden` (`HideViewType = ForceHide/Hide/Unhide`).

### Spawn actor fields (SpawnActorPrototypes) related to placement / respawn
- Placement: `PositionX/Y/Z`, `RotatorAngleYaw/Pitch/Roll`, `SpawnInRadius` (Squad scatter radius, 100-600),
  `AllowSpawnOnIsolatedNavMesh`, `SpawnOnStart`, `LevelName`, `PlaceholderActorGuid`.
- Respawn (Squad): `RespawnMembers`, `MaxRespawnCount`, `InfiniteRespawn`, `RespawnOnNPCCount`,
  `RespawnPoints[]` (`X=.. Y=.. Z=..` strings, picked among), **`MinDistanceToPlayerForRespawn`** (only use:
  `SAP/E11_MQ01_LogicLevel_WP/6B1AB7AF417ADF6D0F72EA8D849EA8CA.cfg:27`, value 300.0).
- Combat tuning: `HP` (100), `DamageMultiplier` (1), `MoveSpeedMultiplier`, `CanBeWounded`, `OverrideRank` /
  `Rank` (no late-game combat squad overrides rank), `OverrideFaction`, `CombatTacticsOverride`
  (`ECombatTactics::None` / `Attack`), `AllowNightVisionForQuestNPC`, `PsyNPCType`
  (`None/PsyNPC/PsyPhantom`), `DisableRagdollForQuestProtection`.
- Triggers: `SpawnType = ESpawnType::Trigger`, `TriggerShape = ETriggerShape::Box`, extents in `ScaleX/Y/Z`.
- Lairs: `RestrictionRadius`, `MinSpawnRank/MaxSpawnRank`, `Volumes`.

### Quest conditions usable for player-relative gating (counts in E06-E16 files)
`Trigger` 1213, `NodeState` 721, **`DistanceToPoint` 593**, `Bridge` 423, `JournalState` 304, `IsAlive` 201,
**`DistanceToNPC` 186**, `GlobalVariable` 129, `IsCreated` 20, **`LookAtAngle` 12** (never on a combat spawn),
`IsOnline` 4, `Awareness` 3. Full enum also has `AITarget`, `EquipmentInHands`, `Radiation`, ...

### A-Life (for completeness)
`ALifePrototypes/ALifePolicyPrototypes.cfg`: `MinRefillDistance = 20000`, `MaxRefillDistance = 25000` (refill
200-250 m from the player), `SeenLongAgoByPlayerSec = 900`, `FarLairDistance = 100000`.
`ALifeDirectorScenarioPrototypes.cfg`: `DefaultSpawnDelayMin/Max = 100/180`, expansion
`DefaultALifeLairExpansionToPlayerTimeMin/Max = 120/180`, per-player-rank archetype limits. Endgame quests set
their zones to `EmptyGroup` (see 0.3).

### What the data says about "spawning behind the player"
- Respawning squads pick a random `RespawnPoints` entry with no player-distance or line-of-sight check unless
  `MinDistanceToPlayerForRespawn` is set (E06_MQ03_C03 points are scattered over the whole yard; E14 Kupol's 2nd
  point is ~100 m from the first; E14 Korshunov points 2-5 m apart).
- Trigger-chained squads are mostly placed 10-30 m from the trigger the player crosses (E16 Granite, E16_MQ01_C01,
  E14 Kupol cabin), i.e. close-range in rooms; some are 50-125 m away and below/behind (E15_MQ03 8_Ground 123 m and
  26 m lower; E06 yard 120 m; E14_MQ01 snipers ~190 m).
- Level EncounterNPCSpawners and Faust controllers choose their own points (level data, not visible in cfg).

## 4. Enemy prototypes, rank and weapons
Definitions: `ObjPrototypes/GeneralNPCObjPrototypes.cfg` (Monolith L410-L440, Varta L843-L879, Spark L985-L1012,
Corpus L1060), `ObjPrototypes/Granit.cfg` (Granit L1, CC L68, Storm L73, Sniper L78),
`ObjPrototypes/QuestObjPrototypes.cfg:1479` (`MonoGausSniper`). Generic NPCs carry no rank in their prototype and
the late quest squads do not override it; **their weapons are chosen by the PLAYER's rank**
(`ItemGeneratorPrototypes/DynamicItemGenerator.cfg`):

| Prototype | Item generator (line) | Primary weapon at player rank Master (Veteran) |
|---|---|---|
| GeneralNPC_Monolith_Stormtrooper | L5827 | G37, Fora, Lavina, Grim, Kharod, **Gauss** (Veteran: G37/M16/Fora/Grim) |
| GeneralNPC_Monolith_Recon | L5647 | Integral, Zubr, Bucket, Fora-230, **Gauss** |
| GeneralNPC_Monolith_Sniper | L6007 | Mark, **Gauss**, M701, SVU, GP3A (Veteran: SVDM/Mark/M701/SKP) |
| GeneralNPC_Monolith_CloseCombat | L5451 | M860, SPSA, D12, Ram-2 shotguns |
| Granit_Stormtrooper (170 HP, shield, dash) | L17733 | Lavina, Grim, Kharod (all ranks) |
| Granit_Sniper | L17660 | **Gauss** (all ranks) |
| Granit_CloseCombat | L17833 | SPSA, D12, Ram-2 (all ranks) |
| GeneralNPC_Varta_Stormtrooper | L8553 | Kharod, Dnipro, Fora, G37, Arev |
| GeneralNPC_Varta_Heavy | L8981 | **PKP machine gun** |
Monolith also get `GeneralNPC_Monolith_Armor`, NVG and pistols. Faust clones: `FaustMonolith_CloseCombat` /
`_Stormtrooper` (L2845/L2855). Phantoms: `PhantomNPC_*` (L2977+), ability `Human_PhantomAttack` on every human NPC.

## 5. Levers for a "quest battle fixes" mod (cfg-only, all patchable)
1. Respawning squads: patch `InfiniteRespawn = false`, lower `MaxRespawnCount`, raise `RespawnOnNPCCount`, add
   `MinDistanceToPlayerForRespawn` (e.g. 3000-4000) on: `SAP/E06_MQ03_LogicLevel_WP/{09C162B8...,B6F62575...,
   E9738C26...,FAAFDAB1...}`, `SAP/E07_MQ05_LogicLevel_WP/6C86405D...`, `SAP/E14_Bossfight_Korshunov_LogicLevel_WP/
   {2DE80184...,C4A60205...,3570516E...}`, `SAP/E14_MQ02_LogicLevel_WP/BB79A282...`. Needs the
   `NodePrototypeAppliedMods` bump for existing saves (`harness/docs/cfg-reference.md` "Spawn actors on existing
   saves"). Whether the engine honours `MinDistanceToPlayerForRespawn` on every squad is unverified (one vanilla use).
2. Faust clones: patch the `SetGlobalVariable_Faust_Clone_*` nodes (count 5 -> 2-3, delays 1-2 s -> 5-8 s) in
   E07_MQ05/E07_MQ06/E08_MQ04_C02/C03/E08_MQ05_C01/C02.
3. Big squads: shrink `SpawnedGenericMembers` counts / remove `SquadMembersQuestSIDs` entries (E12_MQ01 6+6+6,
   E14_MQ01 6 snipers, E15_MQ03 16-man 8_Ground, E16 Granite Snipers 5 / SqTen 6).
4. EncounterNPCSpawners (E15_MQ01_C02 loop, E14 Kupol, E14 Richter, E06 AfterSignal): can be throttled from cfg
   only by removing/re-gating the `EnableSpawnReceiver` SendSignal nodes or not relaunching `Container_2` in
   E15_MQ01; their contents need an editor inspection of the level actors first (kit-first rule).
5. Gear: optional per-rank weapon tables (Gauss on generic Monolith at Master).
