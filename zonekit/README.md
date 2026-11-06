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
- Cooked and installed 2026-11-06 08:58 (dev pak `zzz_ImmersiveBattleFixes_30_P`, 32 loose cfgs: 31 actor patches +
  1 quest patch). Waiting on the tester's run from the 2026-09-23 21:26 save.

## 2026-11-06 — MCM design (tester: "add MCM support so people can tune our default values and use toggles")
- MCM lives in Blueprint at runtime; our patches are cfg read at load. Bridge: our own global variables
  (`GlobalVariablePrototypes` patch, defaults = our defaults, so the mod works without MCM), set by setter nodes
  (`SetGlobalVariable`, no launchers) in a `rootgraph` patch that the provider starts with `CppMediator.StartQuestNode`
  (+ `ExecuteConsoleCommand XStartQuestNodeBySID` as a twin). Neither is proven from Blueprint yet.
- Retail exe console commands for globals: only `XSetGlobalBool` and `XSetGlobalObjectPath` exist (no int setter).
- MCM's own `MCM_Restart` quest (OverrideContent loose cfg) is never started by its Blueprints.
- Enemy counts: the default stays b1's data trim. "Fewer" / "Vanilla" add members back at runtime: an `If` on the
  variable (missing variable = True = our default, `cfg-reference.md`), then `Spawn` of the member's own Obj spawn
  actor + `AddOrRemoveFromSquad` into its vanilla squad. Kit evidence: vanilla despawns single squad members in 60
  nodes and still waits on the squad's death (E06_MQ02, SQ103); `AddOrRemoveFromSquad` used 10 times (E03_MQ01).
- Node toggles (Granite ambush): the vanilla node keeps its vanilla fields and is relaunched through an `If` (False =
  vanilla); our changed copy runs on True.
- Not changeable from MCM: spawn actor data read at spawn (`DamageMultiplier`, respawn fields).

## 2026-11-06 — build 2 prepared (MCM; not cooked: waits for the b1 test)
- `gen_patches.py` b2 (subagent, reviewed): 55 files, 67 new quest nodes for Granite (16 If + 21 Spawn + 21
  AddOrRemoveFromSquad, 2 If + 2 node copies for the ambush toggle, 5 setters). Counts: much fewer 18 / fewer 29 /
  vanilla 39. The 2 s Technical delay before AddOrRemoveFromSquad was dropped: vanilla E07_DugaAssault_C01 adds 54
  spawns to squads from the same launcher as the Spawn. Added-back members also get DamageMultiplier 0.65.
  `StartDelay` exists only on Technical nodes in vanilla. Not yet written into the kit (`--dry` only).
- `CppMediator.StartQuestNode(SID)`: SID is the struct `/Script/Stalker2.PrototypeSID`, text form `(Value="X")`
  (editor import_text); no BP make node, so each setter is its own call with a literal SID.
- Assets made in the open editor (`setup_assets.py` via ue_exec): `Runtime/BP_ImmBFSubsystem`, `BP_ImmBFMCM`
  (vars Registered, GraniteEnemies 0, GraniteNoAmbush true), header textures copied from MCM_ModExample1.
  `.uplugin` got the optional ModConfigurationMenu dependency; NewPackages lists the five packages.
- `gen_mcm.py` -> `zonekit/paste/<BP>/EventGraph.txt` (subsystem 21 nodes, provider 39). All function references
  checked in the editor.
- Open: does a setter re-run after it ran once (Fewer -> Much fewer -> Fewer)? Do squad-wide orders given at spawn
  (elites Stay / ForceHide, Kill) reach members added back? Squad-wide despawns and added members.

## 2026-11-06 — build 1 tested: checkpoint-granite
- Noah: "granite is definitely fixed and better". The 10% probe CC: "didn't notice" (no answer on the direction of
  `DamageMultiplier`). Also: "there are still a lot of enemies on the wish granter fight" = the illusion fight
  (E06_MQ02_C02), not touched by any build yet. Checkpoint on his word ("checkpoint it").
- Git on Windows: the spawn actor patch paths are over 260 characters; `git config core.longpaths true` in the repo.

## 2026-11-06 — build 2: Wish Granter illusion (E06_MQ02_C02), encounter spawner off
- Noah: "there are still a lot of enemies on the wish granter fight", "in the wish granter fight enemies still spawn
  behind you"; asked which: the illusion fight.
- Kit: E06_MQ02_C02 (container `E06_MQ02_Container_IllusionFight`, launched after `E06_MQ02_Technical_CombatTime`)
  is a 2-minute survival: `Spawn_AgressiveVarta` (squad EEE2DEAC, 5 Ward Recon; member [0] and [4] are the same
  GUID) at the illusion start, then 2 s after CombatTime `SendSignalIllusionVartaEnableSpawnReceiver` (receiver
  0B20CD93) switches on a level encounter spawner; `Technical_Delay2` (120 s) -> Ward neutral -> despawn signal ->
  End. Nothing waits for kills, so the spawner can go without stalling anything. Retail 2.1 has the same 16 nodes.
- Change: the SendSignal's only launcher is now `E06_MQ02_C02_Technical_Debug` (vanilla, no launchers, never runs).
  Squad and timer stay vanilla. `gen_patches.py --only E06_MQ02_C02` wrote just this file (the Granite files in the
  kit are still checkpoint-granite's; the MCM cfg stays unwritten). The kit plugin also holds the empty MCM
  Blueprints (no graph, no WorldSubsystemData: inert in this cook).
- Cooked and installed 09:33 (override pak: 33 cfgs = checkpoint-granite's 32 + this one). Test save: 2026-11-06 00:08 (`4E39ECB3`: illusion container named, `E06_MQ02_C02_Start` not yet).
