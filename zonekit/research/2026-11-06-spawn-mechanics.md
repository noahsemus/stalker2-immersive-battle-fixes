# Quest-battle spawn mechanics: what controls them, and what a mod can change (research 2026-11-06)

Sources: kit cfgs `G:/Epic Games/STALKER2ZoneKit/Stalker2/Content/GameLite/GameData/` (abbreviated `GD/`),
`bp_api_dump2.txt`, the retail exe's strings (`Stalker2-Win64-Shipping.exe`, 174,735,920 bytes, 2026-10-30), and
the paks installed under `~mods`. Everything here comes from reading data. **Nothing was tested in game.** Field
meanings that come only from a name are marked *(inferred)*. The kit's cfgs can differ from retail: read the
retail pak's copy before relying on any number.

Census scripts (scratchpad): `scripts/nodefields.py` (every field and value of the quest nodes of given NodeTypes)
and `scripts/sapcensus.py` (every field of the spawn actors, grouped by SpawnType). Raw output:
`sap_endgame.txt` (the E14-E16 / C_E15 logic levels) and `sap_all.txt` (the whole SpawnActorPrototypes tree).
`exe_strings.txt` holds the ASCII and UTF-16 strings of the retail exe. `modcfgs.txt` lists every cfg in every
installed mod pak, and `modx/` holds the extracted mod paks.

---

## 1. Schemas

### 1a. Quest `Spawn` node (4,605 vanilla nodes): it holds almost nothing
Every field that appears across all 4,605 `EQuestNodeType::Spawn` nodes in `GD/QuestNodePrototypes/`:

| Field | Values seen (count) |
|---|---|
| `SID`, `QuestSID`, `NodePrototypeVersion` (1..9), `Launchers`, `Repeatable` (16x true), `BrokenGameDataFilter` (`UnderDraftComment`) | the usual node bookkeeping |
| `TargetQuestGuid` | GUID of a **SpawnActorPrototype** (squad / NPC / item ...). 13 are empty. |
| `IgnoreDamageType` | `EIgnoreDamageType::None` (4199), `Invulnerable` (288), `Unkillable` (74), `Unfocusable` (44). `IgnorePSY` exists only on SetCharacterParam. |
| `SpawnHidden` | false (4544), true (50), 0 (11) |
| `SpawnNodeExcludeType` | `ESpawnNodeExcludeType::SeamlessDespawn` (3785), `ForceDespawn` (621), `KillSpawnedObj` (199). The exe has exactly these three. |

Example (`GD/QuestNodePrototypes/E16_MQ02.cfg:70-96`):
```
E16_MQ02_SpawnObjectNPCMonster_BP_Squad_InitialMonolith : struct.begin
	NodeType = EQuestNodeType::Spawn
	Launchers : [0] {Excluding=false, Connections [0] SID = E16_MQ02_Trigger_InitialMonolithSpawn}
	            [1] {Excluding=true,  Connections [0] SID = E16_MQ02_OnTriggerEnterEvent_Despawn1stSquad}
	TargetQuestGuid = 7C5E18F749F0DB5D5D7C6583D074E1DF
	IgnoreDamageType = EIgnoreDamageType::None
	SpawnHidden = false
	SpawnNodeExcludeType = ESpawnNodeExcludeType::ForceDespawn
```
A Spawn node has **no count, distance, visibility, radius or "away from player" field**. Who spawns and where lives
entirely in the spawn actor named by `TargetQuestGuid`. Waves come from the graph itself: Trigger or
OnNPCDeathEvent → next Spawn node.

Related node types use the same short schema:
- `Despawn` (1118): `TargetQuestGuid`, `SpawnNodeExcludeType` (ForceDespawn 648 / SeamlessDespawn 354 /
  KillSpawnedObj 116), `SpecificItemDespawn`.
- `SpawnSquad` (15), `SpawnSingleObj` (44), `SpawnLair` (1): the same fields as Spawn.
- `OnNPCDeathEvent` (1061): `EventType = EQuestEventType::OnObjDeath`, `TargetQuestGuid` (a squad or NPC spawn actor),
  `LaunchOnQuestStart` (true in 1059 of them), `TrackBeforeActive`. This is how waves advance. In `E16_MQ01_C03`, 15
  Spawn nodes and 20 OnNPCDeathEvent nodes chain off each other, and the death targets checked
  (`B199C7E2...`, `29525D88...`) are **squads**.
- `SetCharacterParam` (678): `Params[n].ModifiedCharacterParam` = HP, HPPercent, IgnoreDamageType, Zombie, Rank,
  Money, Bleeding, Radiation, HungerPoints...; `ChangeValueMode` Set / Add / Subtract; `ChangeValue`; `Rank`.
- `SetCharacterEffect` (68): `EffectPrototypeSID`, `TargetQuestGuid` (65 of the 68 target the player
  `AAAA...`).
- `SetAIBehavior` (6300): `BehaviorType` (Stay / Kill 905 / MoveTo / Patrol / ShootTarget ...), `GoalPriority`,
  `ImmediatelyIdentifyEnemy` (true in 800 of the 835 nodes that set it), `IgnoreCombat`, `MovementType`
  (Walk / Run / Sprint), `MoveToPath`, `Radius`. Wave squads are usually given `Kill` with
  `ImmediatelyIdentifyEnemy = true`, so they know where the player is the moment they spawn.
- `ALifeDirectorZoneSwitch` (48): `TargetQuestGuid` (an ALifeGroup spawn actor), `NewZoneState`,
  `OverrideScenarioGroupSID` (EmptyGroup 34, Emission 8, Hub 4, Quiet 1, ContextualActions 1).
- `ToggleLairActivity` (488): `Activate`, `ForceDespawn`.
- `SetNPCSequentialAbility` (13): `AbilityPrototypeSID` (e.g. `Human_CombatPSYAttack`, `Strelok_SpawnAnomaliesAbility`),
  `SequentialAbilityModificationMode` (`EModifyAbilitySequenceQuestNodeMode::AddAbility` / `RemoveAbility`),
  `SequentialAbilityPriority`.

### 1b. The spawn actors (`GD/SpawnActorPrototypes/WorldMap_WP/<level>/<GUID>.cfg`)
Endgame logic levels: `E14_MQ01/02`, `E14_Bossfight_Korshunov`, `E15_MQ01/02/03`, `E16_MQ01` and its `_C01.._C04`,
`E16_MQ02`, `E16_MQ03`, `E16_Bossfight_Scar`, `E16_Bossfight_Strelok`, `C_E15_MQ03_1_LastDesire`,
`C_E15_MQ03_1_TheHardestChoice`, `C_E15_MQ04_ZoneNotbeFree` (all `..._LogicLevel_WP`). Together they hold
1,244 GUIDs: 357 Obj, 89 Squad, 326 Trigger, 6 ALifeGroup and others.

**`ESpawnType::Squad`** (1,292 in the whole tree; every field seen):
```
SpawnType = ESpawnType::Squad
SpawnOnStart = false                      // quest squads wait for a Spawn node
PositionX/Y/Z, Rotator*, Scale*           // the squad's anchor point
SpawnInRadius = 100.0                     // members scatter this far around the anchor (cm). 100 (817x), 300, 400, 638, 500, 1000 ...
SquadMembersQuestSIDs { [0] = <GUID> ...} // named members: each is its own ESpawnType::Obj actor
SpawnedGenericMembers { [n] { SpawnedSquadMembersCount = N   SpawnedPrototypeSID = <ObjPrototype> } }   // generic members
SpawnedPrototypeSID = Empty
OverrideRank = false / Rank = ERank::...  OverrideFaction = <faction>
RespawnMembers = true|false               // waves inside a single squad
MaxRespawnCount = N                       // 0 (114x), 1, 2, 3, 5
InfiniteRespawn = true|false              // 103 true across the tree
RespawnOnNPCCount = N                     // respawn when this many remain (inferred)
RespawnPoints { [0] = X=... Y=... Z=... } // where respawned members appear (exe: "Placeholder %s cannot respawn members due to empty respawn points")
MinDistanceToPlayerForRespawn = 300.0     // used ONCE in vanilla: WorldMap_WP/E11_MQ01_LogicLevel_WP/6B1AB7AF417ADF6D0F72EA8D849EA8CA.cfg
AllowSpawnOnIsolatedNavMesh = false
CombatTacticsOverride = ECombatTactics::None | Attack | Hold
AllowNightVisionForQuestNPC, DisableRagdollForQuestProtection, EnableSmartLootIfPossible, MainInfoTopicOwner,
VolumetricCoverRestrictions { bEnabled, Volumes }, LairPrototypeSID (2x), SpawnedSquadMembersCount (4x)
NodePrototypeVersion, NodeCreationVersion
```
Endgame respawning squads:
- `E14_Bossfight_Korshunov_LogicLevel_WP/2DE801844AAD3B10E247BC82E80C8DFB.cfg`: 1 Varta Recon + 1 Stormtrooper,
  `RespawnMembers = true`, `MaxRespawnCount = 3`, **`InfiniteRespawn = true`**, two RespawnPoints about 1-4 m from the
  anchor. The same level also has `3570516E...` and `C4A60205...`.
- `E14_MQ02_LogicLevel_WP/BB79A282488ED4F6B3B07D9241F4FE87.cfg`: 8 named members, `MaxRespawnCount = 2`,
  `RespawnOnNPCCount = 2`, RespawnPoints `X=229435 Y=126798` / `X=233884 Y=135911`.

**`ESpawnType::Obj`** (one NPC; 4,204 in the tree; the fields relevant here):
```
SpawnedPrototypeSID = GeneralNPC_Monolith_Recon     // the ObjPrototype
HP = 100                     // 100 in 4165; others 150, 10, 500, 1000, 200, 1 ... (percent? inferred)
DamageMultiplier = 1         // 1 in 4203, 2 once. Per-NPC outgoing damage (inferred)
MoveSpeedMultiplier = 1.0    // 2.0 four times
PsyNPCType = EPsyNPCType::None | PsyNPC (6) | PsyPhantom (4)
CanBeWounded, OverrideRank / Rank, OverrideFaction, CombatTacticsOverride (None / Attack 14 / Hold 3),
AllowSpawnOnIsolatedNavMesh, VolumetricCoverRestrictions, AllowsQuestSave, DataLayers
```
Base defaults: `GD/SpawnActorPrototypes.cfg:1-21` (`HP = 0`, `DamageMultiplier = 0.f`,
`MoveSpeedMultiplier = 0.f`, `PsyNPCType = None`).
Endgame Obj actors: all 357 have `DamageMultiplier = 1`, `HP = 100`, `MoveSpeedMultiplier = 1.0`; 47 set
`OverrideRank` (38 of those Master). The most common prototypes are `GeneralNPC_Monolith_Stormtrooper` (44),
`_Recon` (42), `_CloseCombat` (27), `_Sniper` (26), `Granit_Stormtrooper` (18), `GeneralNPC_Spark_*`.

Other spawn types that matter here:
- `ESpawnType::Trigger`: `TriggerShape` (Box / Freeform / Cylinder), position and scale = the volume that fires
  the wave.
- `ESpawnType::ALifeGroup` (87): `ALifeScenariosGroupSID` (EmptyGroup, Hub, Quiet, Global...),
  `ScenariosGroupPriority` (`EALifeGroupPriorityType::Quest` / `Local` / `Global`), a trigger shape. Only E14_MQ02
  and E15_MQ01-03 place one in the endgame. **E16 has none.**
- `ESpawnType::OnlineModifierZone` (25): `OnlineModifierDistance`, `GlobalOnlineModifierDistance`.
- `ESpawnType::PsyAnomaly` (91), `PSYControllerAnomaly`, `LairSpawner`, `MoveToPath`.

### 1c. Psy phantoms (three sources)
1. **The player's own PSY meter** (the main source). The player's `ApplicableMechanicsEffects` include
   `PsyMechanics` (`GD/ObjPrototypes.cfg:748`). `GD/EffectPrototypes.cfg:4014` PsyMechanics: `PhaseFour`
   (`ConditionValue = 85`, line 4023) applies `ConditionalSpawnPSYPhantoms`, and `PhaseTwo` (30, line 4065) applies
   `ConditionalSpawnPSYNPC`. Both are `EEffectType::Conditional` (`EffectPrototypes.cfg:25436-25453`): they spawn
   unless the player has the flag `BlockPSYPhantomsSpawns` / `BlockPSYNPCSpawns` (lines 25454-25467; the bool
   providers live in `GD/BoolProviderPrototypes/EffectBoolProviderPrototypes.cfg:13-22`). **No vanilla quest applies
   these flags.**
2. The spawn effects (`EEffectType::SpawnPsyPhantoms`):

| Effect (EffectPrototypes.cfg line) | PsyNPCType | Player distance min/max (cm) | Gap between phantoms | Cycle delay (s) | Time between spawns (s) | Count min/max | Pool |
|---|---|---|---|---|---|---|---|
| `SpawnPSYPhantoms` (6694) | PsyPhantom | **1000 / 1500** | 400 / 500 | 7-12 | 1-4 (despawn 1-2) | **4 / 6** | Blinddog, Bloodsucker, Boar, Flesh, Tushkan, `PhantomNPC_*` |
| `SpawnPSYNPC` (6752) | PsyNPC | **1000 / 1500** | 300 / 500 | 5-12 | 1-2 | 1 / 2 | 18 `PsyNPC_<faction>_<role>` (`GeneralNPCObjPrototypes.cfg:2866-2976`, BP `BP_AI_Human_PSYNPC`) |
| `WanderingLightSpawnPSYPhantoms` (16071) | PsyPhantom | 1000 / 1500 | 400 / 500 | 30-60 | 30-60 | 1 / 1 | mutants only |

   - **Direction:** `GD/CoreVariables.cfg:683-714` `WeightAzimuthArrayPsyPhantom`: weights per azimuth band, 0-30°
     0.5, 30-150° 1.0, 150-180° 0.5, 180-210° 0.25, 210-330° 0.1, 330-360° 0.25. Where 0° points is not known
     *(inferred: relative to the player's view; asymmetric as written)*. One global array. It decides whether
     phantoms appear behind the player.
   - Phantom traits: `ObjPrototypes.cfg:383-395` `SpawnPhantomParams` (BP `BP_AI_PsyPhantomHuman`, permanent
     effects: movement -50%, bullet speed 92%, `ProtectionStrike -80%`; overlap PSY damage).
     `CoreVariables.cfg:13` `PsyNPCCorpseTimeout = 5`, `FaustCloneCountCap = 20`.
   - Difficulty scaling: `DifficultyPrototypes.cfg:584-599`, `Stalker` (Master) only.
     `PsyPhantomNPCOverrides [*] { OverrideEffectPrototypeSID = SpawnPSYPhantoms / SpawnPSYNPC;
     PSYDelayBeforeNewSpawnCycleModifier = 0.5; PsyPhantomNPCCountMultiplier = 2.0; bPsyNPCApplyBleeding = true;
     PsyNPCDurabilityDamageMultiplier = 2.0 }`. On Master the waves are 2x the size and twice as frequent.
   - An unused vanilla effect, `PsyNPCsSpawnBlockEffect` (`EffectPrototypes.cfg:26539`,
     `Type = EEffectType::PsyNPCsSpawnBlock`, permanent), is a third blocker.
3. **Placed psy NPCs**: Obj spawn actors with `PsyNPCType = PsyNPC/PsyPhantom` (`E06_MQ02` 5x, `SQ103`, the demo
   map). None are in the endgame levels. The CNPP Blueprint class `CNPPArchAnomalyBase` (`bp_api_dump2.txt:1786-1805`)
   exposes `max_phantoms`, `phantom_patrol_radius`, `phantom_wait_time_min/max`, `spawn_phantom`,
   `despawn_phantoms`. These are Blueprint properties (asset data, not cfg). Changing them would mean overriding that
   Blueprint asset, which is a conflict cost.

Console (debug): `XSpawnPsyNPC bIsPsyPhantom ObjPrototypeSID Rank Count`,
`XSetPsyNPCFilterParams ...`, `XTogglePsyPhantomDebugMode` (`harness/docs/console-commands.md`).

## 2. Global spawn settings relative to the player

| Setting | File:line | Vanilla | Applies to |
|---|---|---|---|
| `MinALifeSpawnDistance` | `GD/AIGlobals.cfg:12` | 2500 (25 m) | A-Life director / lair spawns (not quest placeholders) |
| `MinALifeDespawnDistance` | `AIGlobals.cfg:13` | 3000 | A-Life |
| `MaxAgentsCount` | `AIGlobals.cfg:14` | 52 | global online-agent cap |
| `TimeToSkipLairPeacefulSpawnAfterMemberDies` | `AIGlobals.cfg:24` | 10.0 | lairs |
| `ALifeGridVisionRadius` / `GenericModelGridVisionRadius` | `GD/CoreVariables.cfg:7,9` | 8500 / 7500 | online bubble |
| `AgentSpawnNavMeshQueryDistance` | `CoreVariables.cfg:10` | 250 | navmesh snap of a spawn point |
| `TraceCheckLengthOnSpawn` / `MinDistanceToFloorOnSpawn` | `CoreVariables.cfg:595-596` | 600 / 20 | spawn floor trace |
| Dynamic A-Life streaming distance | `CoreVariables.cfg:871-888`, `SettingsVariablesPC.cfg:128-133` | 100-200 m | online/offline switch |
| Director preset | `GD/ALifePrototypes/ALifeDirectorScenarioPrototypes.cfg:1-17` | `DefaultSpawnDelayMin/Max = 100/180`, `DefaultPostSpawnDirectorTimeoutMin/Max = 150/300`, `FallbackMaxSpawnCount = 3`, `DefaultExpansionSquadNumMin/Max = 4/7` | director scenarios |
| Archetype caps per player rank | same file, 19-296 | e.g. Newbie Human MaxCount 3 | director |
| Scenario groups | same file, 1753-2251 | `Global` SpawnDelay 60-90 s, `Local` 30-60, `Emission` 10-20, `Quiet`, `EmptyGroup` | director |
| Policy | `GD/ALifePrototypes/ALifePolicyPrototypes.cfg` (Default) | `MinRefillDistance 20000`, `MaxRefillDistance 25000`, `FullWipeRefillCooldown 360` | lair refill |
| Exe cvars | retail strings | `ai.SpawnInvisibilityWarmupDuration`, `...MultiplierWhenForceLoading`, `...FixupThreshold`, `GSC.ALife.GameGraphMinComponentVerticesCountForSpawn`, `gsc.Creator.Budget.MaxModelsSpawnPerTick`, `ALife.ExpandToRestingLairs` | engine |

**There is no "spawn out of view" or "not behind the player" rule for quest placeholders.** No cfg field and no exe
string names one (searched: OutOfView, NotVisible, OutOfSight, SpawnBehind, InView, SpawnDistance: only lair /
artifact / VFX hits). A quest squad appears at its fixed anchor ± `SpawnInRadius` the moment its Spawn node fires,
wherever the player is. The only player-relative spawn rules are:
- A-Life: `MinALifeSpawnDistance`.
- Squad respawns: `MinDistanceToPlayerForRespawn` (an exe wide string, so it is read by the parser; used once in
  vanilla, value 300).
- Phantoms: `PhantomPlayerMin/MaxDistance` plus `WeightAzimuthArrayPsyPhantom`.

So "spawned right next to me / behind me" in a quest battle comes from:
- (a) the placeholder anchor or its `RespawnPoints` lying where the player stands when the trigger fires,
- (b) the trigger volume firing while the player is already past the anchor,
- (c) psy phantoms at 10-15 m with azimuth weights that allow behind,
- (d) on E16, unblocked A-Life director scenarios. No ALifeGroup there, and `MinALifeSpawnDistance` is only 25 m in
  vanilla.

## 3. Difficulty and per-battle toning down
`GD/DifficultyPrototypes.cfg` (740 lines): `Empty` (base, 1-80), `Easy` 81, `Medium` 128, `Hard` 164,
`Stalker` (= Master) 209, `Custom` 703, `*_Xbox` 716-730, `Default` 731.
- `NPCCombatDifficulty`: `NPC_HP` (Medium 1.2, Master 1.5), `NPC_Weapon_BaseDamage` (Easy 0.17, Medium 0.85,
  Hard 1.02, Master 1.35), `NPC_Armor_Strike_Add`, `NPC_Weapon_Rank_Add`, `NPC_AttackCooldown`,
  `HipAccuracyMultiplier` (1.0 everywhere), `AccumulatedDamageReductionCurveWeightMax/Min/MaxDistance`,
  `...IncludesHealedHealth`, `PlayerWeapon_HeadshotMultiplier` (Master 2.0), `Weapon_JammingMultiplier`,
  `PsyPhantomNPCOverrides`.
- `MutantCombatDifficulty`: `Mutant_BaseDamage`, `Mutant_AttackCooldown`, `AgentCooldownMultipliers`.
- These are global per difficulty and cannot be scoped to one battle.

NPC accuracy is per weapon, not per NPC: `GD/WeaponData/CharacterWeaponSettingsPrototypes/NPCWeaponSettingsPrototypes.cfg`
(`DispersionRadius`, `DispersionRadiusMultiplierByDistanceCurve`, `BaseDamage`, `FireDistanceDropOff`).
`ObjPrototypes.cfg:252` `FireDispersionParams` and `:500-530` `AgentBehaviourParameters.WeaponHandling`
(`Min/MaxFireCountQueueScaler`, `Far/NearFireQueueDelaySeconds`, `PerBoneIgnoreDispersionModifiers`) sit on the
ObjPrototype. Perception: `VisionScannerPrototypeSID` / `ThreatPrototypeSID` / `HearingSensorPrototypeSID` on the
ObjPrototype (`ObjPrototypes.cfg:~360-377`). `GeneralNPC_Monolith_*` (`GeneralNPCObjPrototypes.cfg:~410-449`) are
shared with every open-world Monolith.

**Levers scoped to a single battle, cheapest first:**
1. Patch the **spawn actor** of each wave member:
   - `DamageMultiplier` (e.g. 0.6), `HP`, `OverrideRank = true` + `Rank = ERank::Experienced`, `CombatTacticsOverride`.
   - On squads: drop entries from `SquadMembersQuestSIDs` (plain-struct replace of the list), lower
     `SpawnedSquadMembersCount`, set `RespawnMembers = false` / `InfiniteRespawn = false` / `MaxRespawnCount`, add
     `MinDistanceToPlayerForRespawn`, move `RespawnPoints`, or move `PositionX/Y/Z` / shrink `SpawnInRadius`.
2. A new ObjPrototype per battle archetype (`ImmBattle_Monolith_Stormtrooper : struct.begin {refkey=GeneralNPC_Monolith_Stormtrooper}`
   in the mod's ModGameData) with a softer `AgentBehaviourParameters.WeaponHandling` / `VisionScannerPrototypeSID`,
   then point the spawn actors' `SpawnedPrototypeSID` (or the squad's `SpawnedGenericMembers[n].SpawnedPrototypeSID`)
   at it. Only quest NPCs change. Caveat: with grEdit installed, whether the child inherits grEdit's bpatch on the
   parent is not verified.
3. Quest graph:
   - Empty a wave Spawn node's `Launchers` (the documented way to disable a node).
   - Remove `ImmediatelyIdentifyEnemy` from a `SetAIBehavior Kill`.
   - Add a `SetCharacterEffect` on the player with `BlockPSYPhantomsSpawns` / `BlockPSYNPCSpawns` /
     `PsyNPCsSpawnBlockEffect` for the battle.
   - Add an `ALifeDirectorZoneSwitch` to `EmptyGroup` (needs an ALifeGroup spawn actor; E16 has none, so the mod would
     add one).
4. Global phantom tuning (affects phantoms everywhere): bpatch `SpawnPSYPhantoms` / `SpawnPSYNPC`
   (`PhantomPlayerMinDistance`, `MaxSpawnPhantoms`, `DelayBeforeNewSpawnCycle*`), the azimuth weights in
   CoreVariables `DefaultConfig.WeightAzimuthArrayPsyPhantom`, or Master's `PsyPhantomNPCOverrides` (lower the 2.0
   multipliers).

## 4. How a mod changes these without whole-file overrides
Rules from `harness/docs/cfg-reference.md` and `config-files.md`, with patterns seen in installed mods:
- **Quest node field patch.** Put `QuestNodePrototypes/<QuestFile>/<QuestFile>_patch_<Mod>.cfg` (folder named after
  the vanilla cfg) in the OverrideContent pak:
  ```
  E16_MQ02_SpawnObjectNPCMonster_BP_Squad_MonolithInTheControlRoom : struct.begin {bpatch}
     Launchers : struct.begin
     struct.end                       // plain struct inside bpatch = replace the list whole (here: empty = node disabled)
  struct.end
  ```
  PIR does exactly this (`QuestNodePrototypes/SmallZone_SQ_L/SmallZone_SQ_L_patch_PIR.cfg`, one field per node with
  `{bpatch}`). Merging is per top-level key: a plain `Key : struct.begin` without `{bpatch}` replaces the whole node.
- **Remove a node:** `<NodeSID> : removenode`. Risky: launchers and conditions elsewhere naming it become dangling.
  Prefer emptying `Launchers`.
- **Add a node:** a new node with `QuestSID = <vanilla quest>` in the same patch file (RAL does this into
  `Garbage_L`), or in the mod's own quest. A node added with `LaunchOnQuestStart` to a quest that has already started
  never launches on that save.
- **Patch a spawn actor.** Two placements are seen in the wild:
  - PIR: `SpawnActorPrototypes/WorldMap_WP/<GUID>/<GUID>_patch_<Mod>.cfg`, i.e. a folder named after the GUID's
    file. For endgame actors that is `SpawnActorPrototypes/WorldMap_WP/E16_MQ02_LogicLevel_WP/<GUID>/<GUID>_patch_<Mod>.cfg`.
  - RAL: `SpawnActorPrototypes/SpawnActorPrototypes_patch_<x>.cfg` holding `<GUID> : struct.begin {bpatch}` keys for
    vanilla GUIDs (e.g. `4BB41B7345F42A8CB86EEBB0AC7A540A`).

  Content: `<GUID> : struct.begin {bpatch} DamageMultiplier = 0.6 ... struct.end`. Lists (`SquadMembersQuestSIDs`,
  `RespawnPoints`, `SpawnedGenericMembers`) are best re-emitted whole as a plain struct inside the bpatch. A single
  index bpatch works on most lists but replaced the whole list once (`PreinstalledAttachments`). `[*]` inside a bpatch
  appends again on every apply.
- **Existing saves.**
  - Spawn actors: an actor that is already spawned is not rewritten from the patch. With
    `NodePrototypeAppliedMods : struct.begin {bpatch} <ModName> : struct.begin NodePrototypeModVersion = N struct.end struct.end`
    on the patched actor, the game deletes it at load and respawns it (`SpawnOnStart`) or spawns it again "when
    needed" (RAL uses this, e.g. `SpawnActorPrototypes_patch_RAL_Core_Buryakivka_Burer1.cfg`). Do not use it on a
    quest squad that is alive on the tester's save mid-battle. Whether a quest-spawned (`SpawnOnStart = false`) squad
    deleted this way comes back, or whether its OnNPCDeathEvent fires, is unknown, and either answer can soft-lock the
    wave. Squads not yet spawned simply use the patched data when their Spawn node fires.
  - Quest nodes: nobody uses NodePrototypeAppliedMods on quest nodes (vanilla or mods). The save stores node
    names and states, so a patched field of a node that has **not run yet** should take effect on an existing save
    *(expected, not verified)*. Nodes that already ran do not run again. `NodePrototypeVersion` exists on every node;
    its effect on saved state is unknown.
- **Pitfalls:**
  - Excluded Spawn nodes despawn what they spawned (every `SpawnNodeExcludeType`). An `End` with
    `ExcludeAllNodesInContainer` therefore despawns the waves. So does an `Excluding = true` launcher, which vanilla
    uses on purpose (E16_MQ02 `Despawn1stSquad`).
  - Waves advance on `OnNPCDeathEvent` of the **squad** GUID. Removing members from a squad is fine. Removing a
    whole squad's Spawn node leaves its death event unfired, so any next wave or objective gated on it never starts.
    Any `OnNPCDeathEvent` or `IsCreated` on an individual member GUID that is removed also never fires. Check every
    reference to a GUID before cutting it.
  - Never chain off a Spawn node's output (`SpawnHook`); launch from its own launchers plus `StartDelay`.
  - A condition naming a missing SID nulls the whole node.
  - Saves hold at most ~65,535 quest-node names, so keep added nodes few.
  - Never ship a whole-file `.cfg`.

## 5. Installed mods (`~mods`, 2026-11-06): what touches these systems
Every `.pak` was listed with the kit's `UnrealPak -List` and the relevant ones were extracted to `modx/`. All the
cfgs found were then checked for the 1,244 endgame spawn GUIDs and for E13-E16 quest or node SIDs.

**Conflicts with endgame quest battles: none direct.** No installed mod patches any E14-E16 quest node or any
endgame spawn actor. The only endgame-named hits are grEdit Better NPC AI Core's patches of the cutscene ObjPrototypes
`C_E14_MQ03_*` / `C_E16_MQ03_Final*_cha_*` (EscapeParameters / ThreatPrototype).

Mods that change the same *systems*, so they interact or compete for the same fields:

| Mod (pak) | What | Relevance |
|---|---|---|
| **Real A-Life QUALITY 2.2.2.12** (`zzzz_RealAlifeMod_QUALITY_2.2.2.12_P.pak`) | `AIGlobals` bpatch `MinALifeSpawnDistance = 9000`, `MinALifeDespawnDistance = 12000`, `MaxAgentsCount = 2200`. Ships a **whole-file `ALifePrototypes/ALifeDirectorScenarioPrototypes.cfg`** (84,852 B) plus about 10 patches of it, ALifePolicy patches, ~27 SpawnActorPrototypes patches (its own and some vanilla GUIDs; `RAL33_QuestSafetyHotfix` disables two infinite-respawn patrols near story areas), GeneralNPCObjPrototypes patches (`RAL34_QualityArchetypes`, 65 KB), A-life_interrupts / Garbage_L quest patches | The whole-file director cfg wins over any director bpatch that loads before it. Raises the online-agent cap (more NPCs near battles). Its 90 m spawn distance already helps against A-Life pop-ins. Patches the generic NPC prototypes our battle NPCs use. |
| Spark Expansion 1.7.10 (installed twice: ABN and ABS) | `MinALifeSpawnDistance = 9000`, ALifePolicy / PopulationManager / GeneralNPCObjPrototypes patches, many spawn actors, `Garbage_L` patch | the same fields |
| RAL add-ons (ABN "All Optional Files": DynamicHub 3.39 **and** 3.42, LivingZone 3.4 **and** 3.5, MutantMovement 1.8 **and** 1.9, RegionalTraffic 1.2 **and** 1.4, RegionalRandomness x2, BanditExpansion 1.6 **and** 1.7, DynamicFrontline, RegionalWarfare, RumorNetwork, PripyatAlive, VartaExpansion, MutantLairExpansion 0.5 **and** 0.7, RankEcology) | Huge `A-life_interrupts` quest patches (up to 12.6 MB), SpawnActorPrototypes patches, `RegionalTraffic` director patch | Open-world A-Life only. Several versions of the same add-on are installed side by side (mod hygiene; worth telling the tester). Pripyat/frontline add-ons may add squads near endgame areas (not checked by position). |
| grEdit ALifeRedux Distance Mild **and** Moderate (installed in both the ABF and ABN folders) | `MinALifeSpawnDistance` 2875 / 3500, `MaxAgentsCount` 60 / 70 | Competes with RAL's 9000 for the same field (last loaded wins). |
| grEdit Better NPC AI 3.1.0 (Core, FactionFlavor, QuestCharacters, CombatDynamics, WeaponCombatDoctrine, ...) | Patches about 1,550 ObjPrototypes (incl. `GeneralNPC_Monolith_*`, `Granit_*`, Faust): `EscapeParameters.FailureChance = 100%`, `ThreatPrototypeSID = DefaultNPC_grEditBetterNPCAI`. AIGlobals threat / grenade / tactics, VisionScanner / Threat prototypes, 46 NPC weapon `CombatSynchronizationScore` patches | Owns NPC perception and tactics. A battle mod should not patch the same ObjPrototype fields; per-battle child prototypes or spawn-actor fields avoid it. |
| aaa_Translucency | `AIPrototypes` `DefaultNPC` vision luminance, AIGlobals cover heights | perception |
| PDAToolsX, Sleeping Bag, PIR NoRegen | `DifficultyPrototypes` bpatches (markers, save types, `Regen_HP`) | no overlap with NPC combat fields |
| PIR | ~6,000 SpawnActorPrototypes item/stash actors, `GeneralNPCObjPrototypes.cfg` (1.6 KB, loot) | items only |

No installed mod touches `SpawnPSYPhantoms` / `SpawnPSYNPC` / `WeightAzimuthArrayPsyPhantom` / `PsyPhantomNPCOverrides`
or `NPCCombatDifficulty`.
