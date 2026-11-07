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

## 2026-11-06 � build 3: the illusion ends when the Recon squad is dead
- Noah (before testing b2): "i don't think you should have to wait at all. you need to end it right after the 5
  soldiers are killed".
- `E06_MQ02_C02_ChangeRelationships_VartaNeutral` (vanilla end chain: Ward neutral -> despawn signal -> End) gets a
  second launcher group [our `OnNPCDeathEvent` on squad EEE2DEAC + `Technical_Delay1`]; the 120 s `Delay2` group
  stays as the fallback. Delay1 in the group: a squad killed before CombatTime must not turn Ward neutral before
  `VartaEnemy` runs (the player would leave the illusion as Ward's enemy). The death event is written like vanilla's
  squad events (LaunchOnQuestStart, OnObjDeath; no Launchers line) and needs a save from before the illusion starts.
- Unknown: the squad lists one member GUID twice ([0] and [4] = 9F617E81); if that keeps the squad's death from
  firing, the 120 s timer still ends it. Cooked and installed 09:37 (3 min cook).
- Build 3 tested (Noah: "nice wish granter stuff worked"): checkpoint-wishgranter. The generator at this commit is
  already the MCM work in progress; build 3's cfgs are the mirrored files under `zonekit/ImmersiveBattleFixes/`.

## 2026-11-06 — build 4 prepared: every fight + MCM (not cooked yet)
- Noah: "let's build the mcm now with all the values for every single fight"; "for the granite fight i don't think
  your numbers are anywhere near correct. i fought like 5-6 people" (true: the Granite squads come one after another
  and earlier ones are despawned by later triggers; menu texts give fractions, not head counts).
- Three research subagents (proposals in the session scratchpad `proposals/group_A|B|C.md`), integrated by a fourth:
  Duga (E07_MQ05/06), Breach (E08_MQ04 + C01/C02/C03, E08_MQ05 + C01/C02; leaf-named members dropped, `leaf_ok`),
  Boundary (whole flank squads held back by Enemies; right-flank distance gate 45 -> 75 m static), Enerhetyk
  (snipers 6 -> 2), Kupol (entrance 8 -> 3, refills off static, spawners toggle), Korshunov (no-respawn static),
  Eye of the Storm (4 phantom spawners toggle), Red Fortress (climb 24 -> 12, the 16-man ground squad toggle);
  finales unchanged (2-5 men per room, nearly all quest-named). Generator: 107 files, 390 new quest node names
  (41 rootgraph setters), 17 MCM settings in story order; validation script found 0 errors.
- Saves: 61.7-61.9k names at the Wish Granter stage (s2sav list 2026-11-06), so ~3.6k headroom before vanilla's own
  growth through the late game.
- Kit: all 107 cfgs written (GameData folder cleared first), provider variables added, paste regenerated
  (subsystem 21 nodes, provider 270). Setter SIDs in the paste = the rootgraph setters (checked).
- Paste round 1: every `StartQuestNode` SID pin came through empty (string defaults survived); fixed with 41
  `Sid_<key>_<value>` PrototypeSID variables (CDO defaults from setup_assets.py, read back: 0 bad) feeding the pins.
  Round 2 checked: 41 SID pins linked, interface present, 34 header-texture pins on our copies.
- Cooked and installed 2026-11-06 17:59: override pak 107 cfgs + WorldSubsystemData; NewContent: subsystem,
  provider, both header textures (the cooked provider imports T_ImmBF_MCMHeader / CatHeader, nothing from the example).
- Saves before fights (name-table scan, approximate): Wish Granter 2026-11-06 00:08; Ward playthrough 2026-09-23:
  Kupol 18:47, Eye of the Storm 20:12, Granite 21:26. None before Duga, Breach, Boundary, Enerhetyk, Korshunov; Red
  Fortress needs a Strider-route save.
- In game: the mod was missing from the MCM menu. Cooked bytecode (zen_kismet): only 11 RegisterModSetting / 11 defaults, no AddUniqueModID. Cause: lifted node names 920+k / 930+k / 940+k collided past 10 settings and the paste dropped the duplicates. Fixed (1000+k / 1100+k / 1200+k / 1300, generator asserts unique names); provider re-paste.
- Re-paste checked in the cooked bytecode (18:16): 17 RegisterModSetting, 17 RegisterDefaultModSetting, 17 GetModSetting, 1 AddUniqueModID, Registered = true, 41 StartQuestNode(this.Sid_*), 41 console twins.

## 2026-11-06 — build 4c: Wish Granter after-illusion blocker (safety net)
- Noah (build 4b, from the 00:08 save): after the illusion he talked to the colonel, "dalin never talked to me. i can
  only ask what's new in the zone", the glass doors to Agatha stayed locked. "please try and make a fix to test".
- Vanilla chain (E06_MQ02): illusion End -> FightIsOver -> StopExperiment -> MonolithEnd -> Dalin + Korshunov
  teleported side by side (660825, 466508 / 466385) -> Comment_DalinAfterMonolith -> FirstDialogDone_1 -> the
  colonel's talk (KorshAfterMonolith, not forced) and Dalin's forced DalinToAgatha (members Zotov FFD8691C, Korshunov,
  Dalin; gated by `_Pin_0` DistanceToPoint <= 4 m at Dalin's spot) -> its last phrase finishes AfterMonolith ->
  OnJournalQuestEvent -> Technical_Agatha (doors Door1 open / unlock, nii_Door_06 unlock). Nothing in E06_MQ02 reads
  the illusion's nodes or its timing besides the container's End, so the cause is not in the data; unknown whether
  vanilla does the same on this save (A/B: both Wish Granter settings Off).
- Safety net (`extra_launchers` on vanilla nodes, groups appended, vanilla groups kept exactly): Dalin's dialog also
  starts 3 s after the colonel's talk ends; AfterMonolith_Fin also runs 45 s after it (doors open, Dalin's line
  skipped). 2 new nodes. Launched from the colonel's talk, so a save already past that talk is not helped.
- Cooked 18:42 (108 cfgs).
- Tested (Noah: "nice, seems to have worked. dalin talked to me"): Dalin's dialog now starts after the colonel's talk (the 3 s nudge; vanilla waits for the player within 4 m of Dalin's spot, which this run never met). MCM toggle test (No reinforcements Off) not reported yet.
- A/B (dev pak removed, 00:08 save): Noah: "dalin doesn't talk to me anymore" = the Dalin blocker happens without ImmersiveBattleFixes too (another installed mod or a game bug; candidates: Sota Increase Dialogue Distance (QuestObjPrototypes), grEdit Better NPC AI (E06_MQ02 scientists), RWNG). The nudge stays as a fix. Door research running.

## 2026-11-06 — build 4d: the projection room door (Agatha)
- Door research (subagent; door actors from the kit's `WorldMap-WindowsModEditor.pak`, receivers matched through the
  `BndEvt__BP_DoorView_<Receiver>` delegates): after the main room the vanilla route to "the meeting in the
  Projection Room" passes `7_1_E06_MQ01_nii_Door_05` (Monolith room exit, 664902, 467996: Agatha unlocks + force
  opens it) and ends at `nii_Door_06` (662081, 474758, 3102; the Agatha scene trigger 070D55E6 sits in its doorway).
  Technical_Agatha only UNLOCKS Door_06 (receiver 9AAA3A2C); no node in the game opens it (Open FBDE6996 / ForceOpen
  39AA10C8 have no sender). SIRCAA_Hub locks Doors 02-06 once at its start logic. Nothing on our illusion path skips
  a door signal.
- Fix (E06_MQ02 `add`, 5 nodes): 2 s after Technical_Agatha, Door_05 unlock -> force open and Door_06 unlock -> open.
  Offer_Fin locks both again later, as vanilla. Not for a save already past Technical_Agatha (console:
  `XTryReceiveSignal <guid>`, unverified).
- Cooked and installed 19:35 (Noah's A/B run without the mod is done).
- Build 4d in game: "doors still locked. it is the doors to b2" (same floor as the colonel, past the main room, the
  objective marker on the door, interact: locked). Follow-up research: no "B2" text in actor / asset names (likely
  texture signage); SIRCAA_Hub's lock logic runs once and no installed mod touches it (RWNG = locres only).
  Candidates: nii_Door_05 (marker on it in the Offer route) or nii_Door_04 (OpenSpace).
- Build 4e (cooked and installed 20:03): the same door signals again from Trigger nodes when the player enters the
  Monolith room (F5931BAD: Door_05 unlock + force open, Door_04 unlock + open) and the corridor before the projection
  room (E70438CB / 525D3CA9: Door_06 unlock + open). Assumption: signals sent while the door actor is not loaded are
  lost (unverified; console `XTryReceiveSignal <guid>` at the door would tell).
- Build 4e tested (Noah: "yay it worked!"): the doors open once he walks up to them, so the far-away signals were most likely lost on unloaded door actors.
