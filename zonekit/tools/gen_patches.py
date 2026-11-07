"""Write ImmersiveBattleFixes' cfg patches into the kit plugin (then mirror_from_kit.ps1 copies them into the repo).

Usage (kit's embedded Python):  python.exe -I zonekit/tools/gen_patches.py [--dry] [--only <Quest>]
(--only: write just that battle's files and no MCM globals / setters, e.g. a fix cooked before the MCM build)
Every patch is a {bpatch} of one vanilla spawn actor or one vanilla quest node, or a new node / global variable; the
vanilla files are read first and every GUID / node / member named here is checked against them, so a typo stops the
run instead of shipping. The output is re-parsed before anything is written (structs closed, launchers resolve).
Battle data lives in BATTLES below; PLAN.md says what each battle needs and why (MCM: PLAN.md § MCM).
"""
import json, os, re, sys

MOD = "ImmersiveBattleFixes"
SETTINGS = os.path.join(os.environ["LOCALAPPDATA"], "stalker2-modding-harness", "settings.json")
KIT = json.load(open(SETTINGS, encoding="utf-8-sig"))["kit"]
GD = os.path.join(KIT, "Stalker2", "Content", "GameLite", "GameData")
OUT = os.path.join(KIT, "Stalker2", "Mods", MOD, "Content", "GameLite", "GameData")
SAP = "SpawnActorPrototypes/WorldMap_WP"
TAG = "ImmersiveBattleFixes b3"

# MCM "Enemies" levels. 0 = much fewer = the trimmed squad lists (pure data, the default); higher levels add dropped
# named members back at runtime. Tier n's members spawn when the variable is >= n (If "Less n" -> False), so the
# levels are cumulative: 2 also spawns tier 1's members. A missing variable reads True = nothing added.
ENEMY_LEVELS = {0: "Much fewer", 1: "Fewer", 2: "Vanilla"}

# ---------------------------------------------------------------------------------------------------------------
# Battle data, in story order (the MCM menu lists the fights in this order). Squads: squad GUID -> members to KEEP
# (vanilla order) or ("generic", count). Members referenced by quest nodes on their own GUID are kept (the generator
# checks this; "leaf_ok": True also lets a battle drop members named only by leaf SetAIBehavior /
# DisableNPCInteraction nodes). Damage (optional): DamageMultiplier on every kept member and on every member MCM can
# add back. mcm: name part of the battle's global variables (ImmBF_<mcm>_Enemies, ...); several quest files of one
# fight share it (their settings must then agree). fight: the MCM category = the fight's name as a player knows it.
# enemies_default (+ enemies_hover, optional enemies_label): the fight has an "Enemies" setting; "counts" (print only)
# when its levels are not member add-backs (Boundary: whole flank waves, Ifs in "add").
# Toggles: MCM bool -> {vanilla node SID: {field: value} or None}; True (the default) runs our changed copy of the node
# (None: nothing), False the vanilla node. Nodes: quest node SID -> {field: value} set by bpatch (not switchable from
# MCM). Relaunch: quest node SID -> its launcher groups, each a list of SIDs or "SID:Name" (any one group starts the
# node; a plain Launchers struct inside the bpatch replaces the list whole); pointing a node at a node that never runs
# switches it off (cfg-reference.md: disable = no launchers). Add: new nodes (suffix, type, launcher groups, fields),
# SID <Quest>_ImmBF_<suffix>; fields ("toggle", name) = an If on that toggle, ("enemies", comparance, n) = an If on the
# Enemies variable (needs both outputs used). Retarget: condition node SID -> (old SID, new SID): its Conditions block
# re-emitted whole with that TargetNode swapped (a toggled node's state readers). Cond_values: condition node SID ->
# {field: (old, new)}, the same re-emit with one value swapped. Actor_fields: spawn actor GUID -> {field: value}
# (static data read at spawn, not MCM; merged into the squad's member-list patch when both exist).
# Battles without "mcm" get no MCM variables.
# ---------------------------------------------------------------------------------------------------------------

# MCM wording shared by the quest files of one fight (a player's view, no head counts the player may never see)
DUGA = {"mcm": "Duga", "fight": "Assault on the Duga", "enemies_default": 0,
        "enemies_hover": "The Assault on the Duga: the Monolith at the barricades and the checkpoint (Ward's route), "
                         "or in the tunnels and the headquarters (Scar's route). Much fewer: about a third of them. "
                         "Fewer: about two thirds. Vanilla: all of them, except a few in Scar's tunnels who cannot "
                         "come back."}
DUGA_GUARD = {"default": True, "label": "No endless guards at the psy lamps",
              "hover": "On: the two Monolith guarding the checkpoint by the psy lamps are not there, and nobody keeps "
                       "coming back in their place until both lamps are broken (on Scar's route, the same guards at "
                       "the checkpoint before you go to sleep). Off: as in vanilla, they keep coming back."}
DUGA_CLONES = {"default": True, "label": "Fewer Faust copies",
               "hover": "When Faust starts sending copies of himself at you. On: at most two come at a time, every 8 "
                        "to 12 seconds. Off: as in vanilla, up to five at a time and much more often (on Ward's "
                        "route every second near the end)."}
BREACH = {"mcm": "Breach", "fight": "Once More unto the Breach", "enemies_default": 0, "leaf_ok": True,
          "enemies_hover": "Once More unto the Breach (Ward) and Happiness for Everyone (Spark): the Monolith in the "
                           "Duga compound, Liter D, the tunnels, the substation and the communication centre. Much "
                           "fewer: about a third of them. Fewer: about two thirds. Vanilla: all of them. The first "
                           "attack you fight off together with Spark always stays complete."}
BREACH_CLONES = {"default": True, "label": "Fewer Faust copies",
                 "hover": "Only if you go in without the psy protection against Faust on your helmet. On: at most two "
                          "of Faust's copies come at a time, every 8 to 12 seconds. Off: as in vanilla, four at a time "
                          "every 2 to 5 seconds."}


def breach_clones(q):
    """the phantom-zone quests' three Faust setters (one zone per file, identical layout in all four): 4 clones every
    2-5 s -> 2 every 8-12 s; re-set every second while the player is in the zone"""
    return {"FewerClones": dict(BREACH_CLONES, nodes={
        f"{q}_SetGlobalVariable_Faust_Clone_Number_1": {"VariableValue": "2"},
        f"{q}_SetGlobalVariable_Faust_Clone_Spawn_Min_Delay": {"VariableValue": "8"},
        f"{q}_SetGlobalVariable_Faust_Clone_Spawn_Max_Delay": {"VariableValue": "12"}})}


BATTLES = {
    "E06_MQ02_C02": {  # Wish Granter illusion (the Ward fight inside the illusion). Vanilla: the 5-man Ward Recon
                       # squad, then 2 s after CombatTime the level's encounter spawner is switched on for 120 s (Delay2)
                       # and keeps spawning Ward around the player; at 120 s Ward turn neutral and despawn (End).
                       # Tester 2026-11-06: "still a lot of enemies", "enemies still spawn behind you".
        "mcm": "WishGranter",
        "fight": "Wish Granter illusion",
        "toggles": {
            # MCM "Ward keep appearing" off (default): the encounter spawner never switches on (None = no copy of the
            # node on True: the vanilla SendSignal only runs on the If's False). Recon squad and timer stay vanilla.
            "NoReinforcements": {"default": True, "label": "No reinforcements",
                                 "hover": "The Ward fight inside the Wish Granter's illusion. On: only the first five "
                                          "Ward soldiers; nobody keeps appearing around or behind you. Off: as in "
                                          "vanilla, more Ward keep appearing for two minutes.",
                                 "nodes": {
                "E06_MQ02_C02_SendSignalIllusionVartaEnableSpawnReceiver": None}},
            # MCM "End when the soldiers are dead" (default on): the If below
            "EndOnKill": {"default": True, "label": "End when the soldiers are dead",
                          "hover": "On: the illusion ends as soon as the Ward soldiers are dead. Off: as in vanilla, "
                                   "it always lasts two minutes.",
                          "nodes": {}},
        },
        "relaunch": {
            # b3 (tester: "you need to end it right after the 5 soldiers are killed"): the vanilla end chain (Ward
            # neutral -> despawn signal -> End) also starts when the Recon squad is dead; the 120 s timer stays as
            # the fallback (a soldier stuck out of reach). The death group also needs Technical_Delay1 (2 s after
            # CombatTime, after VartaEnemy): a squad killed before the fight starts must not turn Ward neutral first
            # and hostile after (the player would leave the illusion as Ward's enemy)
            "E06_MQ02_C02_ChangeRelationships_VartaNeutral": [["E06_MQ02_C02_Technical_Delay2"],
                                                              ["E06_MQ02_C02_ImmBF_If_EndOnKill:True"]],
        },
        "add": [
            # the squad's death, as vanilla writes squad death events (E16_MQ01_C03_OnNPCDeathEvent_Elites; 1,059 of
            # 1,061 vanilla death events use LaunchOnQuestStart, so it needs a save from before the illusion starts)
            ("OnNPCDeathEvent_AgressiveVarta", "OnNPCDeathEvent", [],
             ["LaunchOnQuestStart = true", "EventType = EQuestEventType::OnObjDeath", "TrackBeforeActive = false",
              "TargetQuestGuid = EEE2DEAC40C7F030E43F8B8B59484FBA"]),
            # MCM "End when the soldiers are dead": the squad's death (after Delay1) ends the illusion only when on
            ("If_EndOnKill", "If", [["E06_MQ02_C02_ImmBF_OnNPCDeathEvent_AgressiveVarta", "E06_MQ02_C02_Technical_Delay1"]],
             ("toggle", "EndOnKill")),
        ],
    },
    "E06_MQ02": {  # Wish Granter, after the illusion (tester 2026-11-06, build 4: "dalin never talked to me. i can only
                   # ask what's new in the zone"; the glass doors to Agatha stayed locked). Vanilla: after the
                   # illusion Dalin and Korshunov are teleported side by side; FirstDialogDone_1 sets the colonel's
                   # talk and Dalin's forced "you have a meeting" dialog, gated by a 4 m DistanceToPoint pin at
                   # Dalin's spot; its last phrase finishes the AfterMonolith stage -> Technical_Agatha unlocks the
                   # doors. Cause of Dalin's silence not found in the data. Safety net, always on:
        "extra_launchers": {
            # Dalin's dialog also starts 3 s after the colonel's talk ends (forced dialogs start at any distance)
            "E06_MQ02_SetDialog_E06_MQ02_Dialog_DalinToAgatha": [["E06_MQ02_ImmBF_Delay_DalinNudge"]],
            # and if it still has not run 45 s after the colonel's talk, the stage it would finish is finished
            # anyway (doors to Agatha open; Dalin's line is skipped). Finishing a finished stage again: assumed no-op
            "E06_MQ02_SetJournal_E06_MQ02_AfterMonolith_Fin": [["E06_MQ02_ImmBF_Delay_DoorFallback"]],
        },
        "add": [
            ("Delay_DalinNudge", "Technical",
             [["E06_MQ02_SetDialog_E06_MQ02_Dialog_KorshAfterMonolith:E06_MQ02_Dialog_KorshAfterMonolith_2_57774"]],
             ["StartDelay = 3.0"]),
            ("Delay_DoorFallback", "Technical",
             [["E06_MQ02_SetDialog_E06_MQ02_Dialog_KorshAfterMonolith:E06_MQ02_Dialog_KorshAfterMonolith_2_57774"]],
             ["StartDelay = 45.0"]),
            # build 4d (tester: "now my objective is to get to the projector room and another couple of glass doors
            # are closed"; also without this mod): 2 s after Technical_Agatha its door signals again, unlock first,
            # then open. nii_Door_05 (Monolith room exit): unlock + force open, as Agatha does. nii_Door_06 (the
            # projection room door; the Agatha trigger sits in its doorway): unlock again + open (vanilla only unlocks
            # it, nothing in the game opens it). Receivers matched to the door actors in the kit's world pak
            # (zonekit/README.md). SetJournal_Offer_Fin locks both again later, as in vanilla. Chaining a SendSignal
            # off a SendSignal is vanilla's own pattern (E06_MQ01 nii_Door_02 unlock -> open).
            ("Delay_AgathaDoors", "Technical", [["E06_MQ02_Technical_Agatha"]], ["StartDelay = 2.0"]),
            ("SendSignal_Door05_Unlock", "SendSignal", [["E06_MQ02_ImmBF_Delay_AgathaDoors"]],
             ["SignalReceiverGuid = E423A01A4DCEACD17722D789FE87BE03"]),
            ("SendSignal_Door05_ForceOpen", "SendSignal", [["E06_MQ02_ImmBF_SendSignal_Door05_Unlock"]],
             ["SignalReceiverGuid = ECEBEFF74BAC480C5A8ED0B2E95D3653"]),
            ("SendSignal_Door06_Unlock", "SendSignal", [["E06_MQ02_ImmBF_Delay_AgathaDoors"]],
             ["SignalReceiverGuid = 9AAA3A2C44296096B4BDF99F03A9ECDB"]),
            ("SendSignal_Door06_Open", "SendSignal", [["E06_MQ02_ImmBF_SendSignal_Door06_Unlock"]],
             ["SignalReceiverGuid = FBDE69964FFEA4201A35CEBDB8F3398D"]),
            # build 4e (tester: "doors still locked. it is the doors to b2", same floor, past the main room, the
            # objective marker on the door, interact says locked): the signals above are sent while the player is
            # ~40-80 m from the doors; assumed lost when the door actor is not loaded then (unverified). So the same
            # signals once more when the player walks into the area next to each door (vanilla Trigger layout:
            # E06_MQ02_Trigger_PlayerInsideMonolithRoom; TrackBeforeActive = true also fires if he is already in it):
            # the Monolith room (F5931BAD) -> nii_Door_05 unlock + force open and nii_Door_04 (OpenSpace) unlock +
            # open (vanilla unlocked it in E06_MQ01); the corridor before the projection room (E70438CB / 525D3CA9)
            # -> nii_Door_06 unlock + open.
            ("Trigger_MonolithRoomDoors", "Trigger", [["E06_MQ02_ImmBF_Delay_AgathaDoors"]],
             ["TargetQuestGuid = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "TriggerQuestGuid = F5931BAD40DEC8A5DD4ABC8C684EE142",
              "bTriggersByAnybody = false", "TriggerAction = 0", "RequiredSquadMembers = ERequiredSquadMembers::AnyMember",
              "ReactType = ETriggerReact::ReactOnAlive", "TrackBeforeActive = true"]),
            ("SendSignal_Door05_UnlockNear", "SendSignal", [["E06_MQ02_ImmBF_Trigger_MonolithRoomDoors"]],
             ["SignalReceiverGuid = E423A01A4DCEACD17722D789FE87BE03"]),
            ("SendSignal_Door05_ForceOpenNear", "SendSignal", [["E06_MQ02_ImmBF_SendSignal_Door05_UnlockNear"]],
             ["SignalReceiverGuid = ECEBEFF74BAC480C5A8ED0B2E95D3653"]),
            ("SendSignal_Door04_UnlockNear", "SendSignal", [["E06_MQ02_ImmBF_Trigger_MonolithRoomDoors"]],
             ["SignalReceiverGuid = 31FDA232464AF437F7D7A2AF1DCFE0AB"]),
            ("SendSignal_Door04_OpenNear", "SendSignal", [["E06_MQ02_ImmBF_SendSignal_Door04_UnlockNear"]],
             ["SignalReceiverGuid = 429F756C45785AC7943A80B76037A57A"]),
            ("Trigger_CorridorDoor06", "Trigger", [["E06_MQ02_ImmBF_Delay_AgathaDoors"]],
             ["TargetQuestGuid = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "TriggerQuestGuid = E70438CB438E724F57B01A9483335FC1",
              "bTriggersByAnybody = false", "TriggerAction = 0", "RequiredSquadMembers = ERequiredSquadMembers::AnyMember",
              "ReactType = ETriggerReact::ReactOnAlive", "TrackBeforeActive = true"]),
            ("Trigger_CorridorDoor06_2", "Trigger", [["E06_MQ02_ImmBF_Delay_AgathaDoors"]],
             ["TargetQuestGuid = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "TriggerQuestGuid = 525D3CA942CD4EF9697DCCB92393EB32",
              "bTriggersByAnybody = false", "TriggerAction = 0", "RequiredSquadMembers = ERequiredSquadMembers::AnyMember",
              "ReactType = ETriggerReact::ReactOnAlive", "TrackBeforeActive = true"]),
            ("SendSignal_Door06_UnlockNear", "SendSignal", [["E06_MQ02_ImmBF_Trigger_CorridorDoor06"],
                                                            ["E06_MQ02_ImmBF_Trigger_CorridorDoor06_2"]],
             ["SignalReceiverGuid = 9AAA3A2C44296096B4BDF99F03A9ECDB"]),
            ("SendSignal_Door06_OpenNear", "SendSignal", [["E06_MQ02_ImmBF_SendSignal_Door06_UnlockNear"]],
             ["SignalReceiverGuid = FBDE69964FFEA4201A35CEBDB8F3398D"]),
        ],
    },
    "E07_MQ05": dict(DUGA, **{  # The Assault on the Duga, Ward route: barricades -> psy lamps -> KPP -> hold the KPP
                                # (Faust clones). Group A proposal § 1.1 / 1.6. Kept members: those farthest from where
                                # the player comes in; none of them (kept or dropped) is named by any quest node.
        "level": "E07_MQ05_LogicLevel_WP",
        "squads": {
            "AB13C8FF44D695F712D0389BF9C1277B": ["7246D21A415591F59043839CEB8392CD"],  # Avantgarde: 1 of 4 Storm
            "654BB30B49492026D7546AA4DA5EFD47": ["4B9C2F1C46DE5B18F1B80E8348B4CD28",   # SquadOne: 2 of 4 Storm
                                                 "03D9F7BF46C76CA219938FBA6A6C755C"],
            "4791D538438F773870314E82B800E6BF": ["813EA73244FB25B1805F5482D8D90098"],  # SquadTwo: the Storm (of 2 Sn + St)
            "283BAED443E1FF3E8BD695910C72B55B": ["3226B94E44ACE15E71E0D0889E9C7895",   # SquadThree: Storm + CC (of 3 St
                                                 "DFF962FC44F367CA070CBEA31FB789DD"],  #   + 2 CC), the pair deepest in the KPP
        },
        "toggles": {
            # the 2-man lamp guard (InfiniteRespawn, respawns on its anchor by the KPP entrance) is not spawned at all
            # (its vanilla Excluding group X[Technical_LampsOff] stays on the vanilla node); nothing waits for it
            "NoEndlessGuard": dict(DUGA_GUARD, nodes={
                "E07_MQ05_SpawnObjectNPCMonster_Monolith_InfiniteGuard": None,
                "E07_MQ05_SetAIBehavior_InfiniteGuard_Kill": None}),
            # no 3 + 3 counter-attack spawning 38-41 m behind the KPP middle (HoldKPP_2 hangs off HoldKPP's output:
            # its consumer Technical_Delay_16 runs on the vanilla path only)
            "NoCounterAttack": {"default": True, "label": "No attack from behind at the checkpoint",
                                "hover": "Ward's route: once you and the Ward reach the middle of the checkpoint, no "
                                         "Monolith come at you from the barricades behind you. Off: as in vanilla, "
                                         "two small groups attack from behind.",
                                "consumers_vanilla_only": ["E07_MQ05_SpawnObjectNPCMonster_Monolith_HoldKPP"],
                                "nodes": {
                "E07_MQ05_SpawnObjectNPCMonster_Monolith_HoldKPP": None,
                "E07_MQ05_SetAIBehavior_Mobolith_HoldKPP_Kill": None}},
            # Faust clones 2 at a time every 8-12 s for the whole hold (vanilla 5 every 1-2 s, then 3-5 s, then 1 s):
            # Min_Delay's consumer Technical_Delay_14 (-> 3 / 5 s) runs on the vanilla path only, the climax's 1 / 1 s
            # setters are skipped
            "FewerClones": dict(DUGA_CLONES,
                                consumers_vanilla_only=["E07_MQ05_SetGlobalVariable_Faust_Clone_Spawn_Min_Delay"],
                                nodes={
                "E07_MQ05_SetGlobalVariable_Faust_Clone_Number": {"VariableValue": "2"},
                "E07_MQ05_SetGlobalVariable_Faust_Clone_Spawn_Min_Delay": {"VariableValue": "8"},
                "E07_MQ05_SetGlobalVariable_Faust_Clone_Spawn_Max_Delay": {"VariableValue": "12"},
                "E07_MQ05_SetGlobalVariable_Faust_Clone_Spawn_Min_Delay_2": None,
                "E07_MQ05_SetGlobalVariable_Faust_Clone_Spawn_Max_Delay_2": None}),
        },
    }),
    "E07_MQ06": dict(DUGA, **{  # The Assault on the Duga, Scar route: underground -> headquarters -> outside (Faust
                                # clones). Group A proposal § 1.2 / 1.6. InfiniteGuard (E07_MQ05 level) only toggled.
        "level": "E07_MQ06_LogicLevel_WP",
        "squads": {
            "DC9B638941364144B6538C853A71C5DB": ("generic", 1),  # TinyGroup: 1 of Recon + CC (MCM cannot add back)
            "16FCF0FC460AA0640700A4850F65E263": ("generic", 1),  # Underground: 1 of 2 Recon + 2 Storm (same)
            "BDB224D2469695F09D3A8C8A6B555879": ["677F5E8D4C49A2B54AE1B7806242B320",   # Main: CC + Recon farthest from
                                                 "94D48F45494228A92F5394BCE22D60A9"],  #   the door, of 2 CC + 3 Recon
            "7BCC58AF4779E138BEB467B4A8FEBAFE": ["DFEE385142B5CFAF6F518CB9F2F9B459"],  # FaustFantoms: the Storm next to the Ward
        },
        "toggles": {
            "NoEndlessGuard": dict(DUGA_GUARD, nodes={   # keeps X[OnJournalQuestEvent_E07_MQ06_Sleep]
                "E07_MQ06_SpawnObjectNPCMonster_Monolith_InfiniteGuard": None}),
            "FewerClones": dict(DUGA_CLONES, nodes={
                "E07_MQ06_SetGlobalVariable_Faust_Clone_Number": {"VariableValue": "2"}}),
        },
        "add": [
            # E07_MQ06 never sets the delays (defaults 5 / 8 s): ours, on the FewerClones If's True (the If of the
            # Number copy, launched by Trigger_PlayerOutside; toggle order: NoEndlessGuard = If _1, FewerClones = _2)
            ("SetClonesMinDelay", "SetGlobalVariable", [["E07_MQ06_ImmBF_If_FewerClones_2:True"]],
             ["GlobalVariablePrototypeSID = Faust_Clone_Spawn_Min_Delay", "ChangeValueMode = EChangeValueMode::Set",
              "VariableValue = 8"]),
            ("SetClonesMaxDelay", "SetGlobalVariable", [["E07_MQ06_ImmBF_If_FewerClones_2:True"]],
             ["GlobalVariablePrototypeSID = Faust_Clone_Spawn_Max_Delay", "ChangeValueMode = EChangeValueMode::Set",
              "VariableValue = 12"]),
        ],
    }),
    "E08_MQ04": dict(BREACH, **{  # Once More unto the Breach (Ward). Group A proposal § 2.1 + § 5 (leaf-named members:
                                  # their only references are leaf SetAIBehavior nodes from the squad's create event)
        "level": "E08_MQ04_LogicLevel_WP",
        "squads": {
            "1ED92E7341EA52E29021A79B31F8CACE": ["9893FBDE4BA1F9D29E31599FD94F9485",   # KPP: 2 of 7
                                                 "9126138345EF48C52FC174BE498D69EC"],
            "E8837A6C42F2B98D07A6EB9383CF624B": ["57A7F6A042F385732310B3A1518EFA98",   # Machinegunners: 2 of 6 (57A7F6A0
                                                 "4F90DAF54B1D04C5A1D430B0A0827B15"],  #   is a dialog member: kept)
            "CBAAD5EF479E753BECBAE7BCE18EB317": ["47D33D2E4ECAE42A211C058AA3454D5B",   # RoadToLiterD: 2 of 5
                                                 "DC7ECF434283F2F9757DB6A80C01A07E"],
            "B36BE1AA453A2DF0E20044BC19F2B440": ["60A7F55E4530FDFACAF38E97D57F679E",   # LiterD_Guards: 2 of 5
                                                 "7255702B4C69AC698E6D938D7B2B14AF"],
            "323DDBD44C0B100CCA09B4880617E41D": ["CAE37974419D5C740E0EF48D0781FAD4",   # LiterD_Inside: CC + Storm farthest
                                                 "088FAF6140E42759D7D9F2A964E3D759"],  #   (40-45 m) from the door, of 3 CC + 3 St
            "838BB2D843AB26D180CD70B9B83CBFEB": ["8A738A054054943D25F02EBB1CD007AE"],  # Techtunnel1: 1 of 3
            "4C9317884046808CA99AACB07D5241E3": ["3210947C40FC060B39AD4196326FA994",   # Techtunnel2: 2 of 5
                                                 "D07E3BF34F9E1AE77CD5B9BDEF19BA74"],
        },
    }),
    "E08_MQ04_C01": dict(BREACH, **{  # communication centre, both routes (Floor2_2 stays: both members in Conditions)
        "level": "E08_DugaAssault_LogicLevel_WP",
        "squads": {
            "BA24490249F206739C449185DE509AF0": ["98EE2AE640D61F0F1FCC72B350E09DD2"],  # Commcenter: 1 of 4
            "A4251294483A41B83F46D4BA0A56957B": ["A460998542109355DCF1129E84E1134B"],  # Commcenter_1: 1 of 2 (squad death
                                                                                       #   drives both routes)
            "4F4299244FADA9C20748D582869C82DB": ["82AC454044C24AAE56B4FABE3BCBF164"],  # Floor2: 1 of 3
            "B8B78845414CA6AD4045729028F6A787": ["8F549C6D4C7D4FB762909595AAFB5644"],  # Floor2_1: 1 of 4
        },
    }),
    # Faust phantom zones (only without the psy-resist upgrade): boiler room, cooler + communication centre (Ward),
    # parking, transformer (Spark)
    "E08_MQ04_C02": dict(BREACH, toggles=breach_clones("E08_MQ04_C02")),
    "E08_MQ04_C03": dict(BREACH, toggles=breach_clones("E08_MQ04_C03")),
    "E08_MQ05": dict(BREACH, **{  # Happiness for Everyone (Spark). MonoLightAttack (every member a journal target) stays
                                  # vanilla. AssaultStation_1: the southern pair kept (the northern one spawns on the
                                  # approach path, behind the player at the levers)
        "level": "E08_MQ05_LogicLevel_WP",
        "squads": {
            "BCD38A8D4CAE8626436ED4B5FC8290A0": ["F9C5497D4AB63A8A12259F98A36B22C5",   # KPPDefenders_Decoration: 2 of 7
                                                 "0395EB2D43116A1902E2188BC8DEDFA6"],  #   (F9C5497D has an ItemAdd: kept)
            "9E4858E64C3AAA2BDDFDDCB7EB0ED5C0": ["10C60B614A4B8FB64964F085ADB083BA",   # KPPDefenders_AttackSquad: 2 of 6
                                                 "5E4614AE435E85DE5A86FD8632E4D863"],
            "E87B6EE34442FFD51C5858A26DA7179A": ["0EDFB96C445A757C67209BA33805F2C2"],  # TransformerGuards: 1 of 4
            "5FED25634A7F276CD83FB7A6E942D97C": ["74EB7D32433015FCC16249AD31762269"],  # TransformerGuards_Extra: 1 of 2
            "0257660F4C461D2DDF44978C4F8CBE7C": ["759E118545A2E16544A247A3C790347A",   # MonoAssaultStation_1: the southern
                                                 "A7D4CE004492448F195ECE8512759FD9"],  #   CC + Storm, of 2 CC + 2 St + Recon
            "0289355F481126B95A55D4B74D38D0B7": ["E1D0420A4CAF7BD3CCC7A7A48F7F4419",   # MonoAssaultStation_2: Storm + Recon
                                                 "221B464948D5E5BA005D00BD727A2D78"],  #   of 5 St + 2 Recon
            "39319CB24D8B8F758F7A3EA689ED083F": ["F65C99CF47E4D0CD14B355A2F92EECA7"],  # CommcenterMonoGreetings: 1 of 4
        },
    }),
    "E08_MQ05_C01": dict(BREACH, toggles=breach_clones("E08_MQ05_C01")),
    "E08_MQ05_C02": dict(BREACH, toggles=breach_clones("E08_MQ05_C02")),
    "E12_MQ01": {  # The Boundary: Monolith assault on Yaniv station (group B proposal § 2.1). Every member is named (a
                   # kill counter), so the Enemies levels withhold whole flank waves; the stage ends on the squads that
                   # came. Vanilla: squad 1 (6) at the exit trigger, at your 2nd kill a flank squad (6, right or left by
                   # distance), as soon as it is out the other flank (6).
        "level": "E12_MQ01_LogicLevel_WP",
        "mcm": "Boundary",
        "fight": "The Boundary",
        "enemies_default": 0,   # 0 = first squad only, 1 = + one flank, 2 = vanilla
        "counts": {0: 6, 1: 12, 2: 18},
        "enemies_hover": "The Monolith assault on Yaniv Station (The Boundary). This setting chooses whole squads, not "
                         "single fighters. Much fewer: only the first squad, from the north. Fewer: one more squad "
                         "comes round a flank after your second kill. Vanilla: two more squads, one from each side.",
        "relaunch": {
            # flank 1 loop: only on the If's False (vanilla launchers [Technical_Gate1], [Technical_Delay_12])
            "E12_MQ01_If_DistanceToRight": [["E12_MQ01_ImmBF_If_Flank1:False"], ["E12_MQ01_Technical_Delay_12"]],
            # flank 2 loop (vanilla [Technical_Gate1_1], [Technical_Delay_13])
            "E12_MQ01_If_DistanceToRight_1": [["E12_MQ01_ImmBF_If_Flank2:False"], ["E12_MQ01_Technical_Delay_13"]],
            # end of the fight: vanilla's two groups + "the squads that came are dead" (a Spawn node's output = its
            # squad is dead, vanilla's own use here)
            "E12_MQ01_Technical_YanovMonolithKilled": [
                ["E12_MQ01_SpawnMonolith_1", "E12_MQ01_SpawnMonolith_2", "E12_MQ01_SpawnMonolith_3"],
                ["E12_MQ01_Technical_M_Killer_Yanov"],
                ["E12_MQ01_SpawnMonolith_1", "E12_MQ01_ImmBF_If_Flank1:True"],
                ["E12_MQ01_SpawnMonolith_1", "E12_MQ01_SpawnMonolith_2", "E12_MQ01_ImmBF_If_Flank2:True"],
                ["E12_MQ01_SpawnMonolith_1", "E12_MQ01_SpawnMonolith_3", "E12_MQ01_ImmBF_If_Flank2:True"],
            ],
        },
        "add": [
            ("If_Flank1", "If", [["E12_MQ01_Technical_Gate1"]], ("enemies", "Less", 1)),
            ("If_Flank2", "If", [["E12_MQ01_Technical_Gate1_1"]], ("enemies", "Less", 2)),
        ],
        # static (not MCM): the right flank's gate 45 m -> 75 m from its check point (half its members stand 29 m
        # from that point, so at 45 m they could appear ~16 m from you). 75 + 50 < 127 m between the two points, so
        # the first check can still never fail both. Matters on Fewer / Vanilla only.
        "cond_values": {"E12_MQ01_If_DistanceToRight": {"NumericValue": ("4500.0", "7500.0")},
                        "E12_MQ01_If_DistanceToRight_1": {"NumericValue": ("4500.0", "7500.0")}},
    },
    "E14_MQ01_C01": {  # The Road to the Foundation, Enerhetyk: Monolith attack on the palace (group B § 2.2). Snipers
                       # on the high ground north of it 6 -> 2 (no quest node names any); the 12 attackers stay (named
                       # by objective markers). The snipers' Excluding group (despawn when the attackers are dead)
                       # also goes on the members added back.
        "level": "E14_MQ01_LogicLevel_WP",
        "mcm": "Enerhetyk",
        "fight": "Enerhetyk",
        "enemies_default": 0,
        "enemies_label": "snipers",
        "enemies_hover": "The Monolith snipers on the high ground north of the Enerhetyk Palace of Culture while you "
                         "fight off the attack (they only come if you approach from the north-west). Much fewer: "
                         "about a third of them. Fewer: about two thirds. Vanilla: all of them. The squads attacking "
                         "the building are unchanged.",
        "squads": {
            "7465D86B439E9526EB689F9487094CB6": ["D5AC23864F6CCAF7BAF07BA10D719107",   # Snipers: 2 of 6, ~100 m ahead
                                                 "DD4C07024E29733BBF704C889342DB30"],
        },
    },
    "E14_MQ02_C02": {  # Down Below, Kupol (the way to the Foundation tunnel; group B § 2.3): entrance squad 8 -> 3,
                       # never refills (static), the 4 level encounter spawners off (MCM). Dropped in vanilla order:
                       # 3EAD7209 (t1, 31 m), AC1FD377 (t2, 7.7 m from the entry trigger), 1E09E417 (t1), E6F51C81
                       # (t2), A06B6B64 (t1).
        "level": "E14_MQ02_LogicLevel_WP",
        "mcm": "Kupol",
        "fight": "Kupol",
        "enemies_default": 0,
        "enemies_hover": "Down Below, on the way into the tunnel to the Foundation: the Monolith squad that rushes you "
                         "when you go in. Much fewer: about a third of it. Fewer: about three quarters. Vanilla: all of "
                         "it. With this mod the ones you kill never come back, whatever you choose here.",
        "squads": {
            "BB79A282488ED4F6B3B07D9241F4FE87": ["130EB7C342351CAA6059F195309F0F6A",   # Recon 61 m
                                                 "3C7F74F249456D564F170082BA21BC6D",   # Storm 71 m
                                                 "95C84A3C46EE930DF65535B8B31938E7"],  # CC 61 m
        },
        "actor_fields": {   # static (read at spawn, cannot be MCM): the squad never refills (vanilla: twice, at 2 points)
            "BB79A282488ED4F6B3B07D9241F4FE87": {"RespawnMembers": "false", "MaxRespawnCount": "0"},
        },
        "toggles": {
            # the 4 level encounter spawners are never switched on; nothing waits for their kills
            "NoReinforcements": {"default": True, "label": "No reinforcements",
                                 "hover": "On: no more Monolith keep appearing after the groups you kill there (the "
                                          "snipers at the entrance and the later waves). Off: as in vanilla.",
                                 "nodes": {
                "E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_SnipersKupol1stGroup.EnableSpawnReceiver": None,  # If _1
                "E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_KupolAfterFirstSquadDeath.EnableSpawnReceiver": None,
                "E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_KupolLeftPart.EnableSpawnReceiver": None,
                "E14_MQ02_C02_SendSignal_BP_EncounterNPC_Kupol_Monolith_LastWave_RightPartTopZoneEnableSpawnReceiver": None,
            }},
        },
        "retarget": {   # "the snipers' enable has not run yet" -> "our If (launched like it) has not run yet"
            "E14_MQ02_C02_SpawnObjectNPCMonster_BP_Squad_E14_MQ02_MonolithEnemies_Olimpia_Pin_2":
                ("E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_SnipersKupol1stGroup.EnableSpawnReceiver",
                 "E14_MQ02_C02_ImmBF_If_NoReinforcements_1"),
            "E14_MQ02_C02_SetAIBehavior_BP_Squad_E14_MQ02_MonolithEnemies_Olimpia_Pin_2":
                ("E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_SnipersKupol1stGroup.EnableSpawnReceiver",
                 "E14_MQ02_C02_ImmBF_If_NoReinforcements_1"),
            "E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_SnipersKupol1stGroup.EnableSpawnReceiver_Pin_2":
                ("E14_MQ02_C02_SendSignal_BP_EncounterNPCSpawner_SnipersKupol1stGroup.EnableSpawnReceiver",
                 "E14_MQ02_C02_ImmBF_If_NoReinforcements_1"),
        },
    },
    "E14_Bossfight_Korshunov": {  # Korshunov boss (group B § 2.4): the Ward pair of phase 1 refills forever, the
                                  # phase-2 pairs 3 times each; nothing waits for their deaths. Static, not MCM
                                  # (respawn fields are read at spawn); no quest patch.
        "level": "E14_Bossfight_Korshunov_LogicLevel_WP",
        "actor_fields": {
            "2DE801844AAD3B10E247BC82E80C8DFB": {"RespawnMembers": "false", "InfiniteRespawn": "false",
                                                 "MaxRespawnCount": "0"},   # phase 1 Recon + Storm
            "C4A60205411AA3D77AA54697861E42C5": {"RespawnMembers": "false", "MaxRespawnCount": "0"},  # phase 2 snipers
            "3570516E4ABEFF860BB634B4F469E237": {"RespawnMembers": "false", "MaxRespawnCount": "0"},  # phase 2 Storm
        },
    },
    "E15_MQ01_C02": {  # Eye of the Storm (Ward route; group C § 1). Every run of this container (relaunched 1 s after it
                       # ends, i.e. each time Skif leaves a shelter) switches on the 4 level encounter spawners
                       # BP_EncounterNPCSpawner_E15_MQ01_1..4: psy-phantom mutants, up to 5 alive per spawner, a new one
                       # every 2-4 s, only outside the player's view. Only entering Beta / Gamma switches them off.
                       # Nothing waits for these kills. The relaunch stays: this container also opens Gamma.
        "mcm": "EyeOfTheStorm",
        "fight": "Eye of the Storm",
        "toggles": {
            # the If below; True = the 4 spawners are never switched on and are switched off at every container
            # start (also cleans up a save made with them running)
            "NoPhantomAmbush": {"default": True, "label": "No phantom ambushes",
                                "hover": "On the way between the shelters during the emissions. On: no phantom dogs, "
                                         "boars, fleshes and bloodsuckers keep appearing behind you. Off: as in "
                                         "vanilla, they keep coming every few seconds until you reach a shelter.",
                                "nodes": {}},
        },
        "add": [
            ("If_NoPhantomAmbush", "If", [["E15_MQ01_C02_Technical_3"]], ("toggle", "NoPhantomAmbush")),
        ],
        "relaunch": {
            # enable signals: only on False (vanilla launcher: Technical_3)
            **{f"E15_MQ01_C02_SendSignal_BP_EncounterNPCSpawner_E15_MQ01_{i}EnableSpawnReceiver":
               [["E15_MQ01_C02_ImmBF_If_NoPhantomAmbush:False"]] for i in range(1, 5)},
            # disable signals: the vanilla group (entering Beta / Gamma) + our True output
            **{f"E15_MQ01_C02_SendSignal_BP_EncounterNPCSpawner_E15_MQ01_{i}.DisableSpawnReceiver":
               [["E15_MQ01_C02_Technical"], ["E15_MQ01_C02_ImmBF_If_NoPhantomAmbush:True"]] for i in range(1, 5)},
        },
    },
    "E15_MQ03": {  # The Last Wish, Red Fortress climb (Strider route; group C § 2, option A). Squad_1 (Richter's fight
                   # at the foot, every member named) untouched. Squads 2-7 (placed up the fortress when "Get to the Red
                   # Fortress" starts) 2 of 4 each, all climb snipers out; 8_Ground (16, on the ground 24 m below the
                   # walls, shoots up from below / behind) switchable off. Nothing waits for squads 2-8; the stage ends
                   # at the roof trigger.
        "level": "E15_MQ03_LogicLevel_WP",
        "mcm": "RedFortress",
        "fight": "Red Fortress",
        "enemies_default": 0,
        "enemies_hover": "The Monolith on the walls of the Red Fortress (The Last Wish). Much fewer: about half of each "
                         "group on the climb, no snipers. Fewer: about three quarters. Vanilla: all of them. The group "
                         "at the foot that you fight with Richter always stays complete.",
        "squads": {
            "3207A3754FA8FAAAD430C58F06008668": ["A1A0FC9546D8810A85667FB828193A4E",   # Squad_2: CC + Recon of CC, 2 Sn, Recon
                                                 "2AF85F10442F17B44DD1AC91FB2E5913"],
            "CCB428FD44F53BF62BD5A990A40892AD": ["FE83D6E645C3AE8428D19F9553E89FAA",   # Squad_3: CC + Storm of 2 CC, Sn, Storm
                                                 "FDE0B8644DB3FD904A9724AB8EED1F55"],
            "24717AF044686DD1C295FCA4034391E5": ["BEB0A3CD4040BDF2E94E9EA2999C9C9E",   # Squad_4: Storm + CC of St, Sn, CC, Recon
                                                 "56A5ED5A44E2E4271EE899B247D1A4D8"],
            "6D61ABCB4B84DB68B17BDCB270A74672": ["50596DBE48E07CE978005086CBC31816",   # Squad_5: 2 of 4 Storm
                                                 "06050D444E9C505D84B0E3936F9BE532"],
            "4E7F5FBE4511C7E2DD8B3E97EBAAC1E6": ["351DDC4E42F12444828FBEA086C45ACB",   # Squad_6: Storm + CC of 2 St, Sn, CC
                                                 "D293451A4E719AB5D54FD0913C3A07F6"],
            "C7FD536B457316DE180441B71063B41D": ["9E66CAB14C57C7BB2232BF8269C53EAC",   # Squad_7: Storm + CC of St, 2 Recon, CC
                                                 "25E4E12A4FBE699612D3519E118664FC"],
        },
        "toggles": {
            # the 16-man 8_Ground squad never spawns (None = no copy; the vanilla Spawn runs only on the If's False)
            "NoGroundSquad": {"default": True, "label": "No squad below the walls",
                              "hover": "On: the big Monolith squad that appears on the ground below the walls once you "
                                       "are up the fortress, and shoots at you from below and behind, never comes. "
                                       "Off: as in vanilla.",
                              "nodes": {
                "E15_MQ03_SpawnObjectNPCMonster_BP_SquadMonolith_8_Ground": None}},
        },
    },
    "E16_MQ01_C03": {  # Granite fight at the Generators (every ending). Tester 2026-11-06: heavy cut, 65% damage,
                       # no ambush (elites visible, snipers do not know where you are when they come out).
        "level": "E16_MQ01_C03_LogicLevel_WP",
        "damage": 0.65,
        "mcm": "Granite",
        "fight": "Granite fight",
        "enemies_default": 0,
        # (tester 2026-11-06: "i fought like 5-6 people with our change": the squads come one after another and the
        # earlier ones are despawned as you move on, so no head counts in the menu)
        "enemies_hover": "The Granite fight at the Generators (every ending). Much fewer: about a third of the Granite "
                         "and one Gauss sniper instead of five. Fewer: about two thirds. Vanilla: all of them (two "
                         "generic Granite cannot come back).",
        "squads": {
            "9532FC3A448DD3AB81562D95C91BE9BA": ["9D8254B6458271C223A98DB7AD0B3667"],  # Respawnable: CC (1 of 1)
            "74D8C40A445CCF28988BF7B2ECEF2C7E": ["F09A16114121EFF44C00409243D7D4FE"],  # Respawnable_1: Storm (of 2 Sn + 2 St)
            "C754B6B54A130E3920F8B89A64C6BA7C": ["011CC4E948076BF17D2C2FB0A0A8EB30"],  # SqThree: Storm (has a space restriction) of CC + St
            "EB55A9AC49F72D5E01EB768CB752216F": ["D51DF6C84444635D87DDEDB9AB42548F"],  # SqFour: Storm of Sn + St
            "50A6E9564032C8553B2F8AAB57793064": ["03429CE74D9E342C6D8890A71FEFDD52"],  # SqFive: CC of CC + St
            "C6C7E2D74919ACAEFD460BB01111381C": ["00AF2A234D960C9D1A9BCFA09ED427F7"],  # SqSix: Storm of St, CC, St
            "418687B24CBACA896AC74A8CE7C8A249": ["20F2CE55427FF2AEB99A0F8E496110E7"],  # SqSeven: Storm of St + Sn
            "9CA2F72B413CBCD5B80B59ADBCC9A20E": ["4116388D4891565BF43F7CA4D764EDC7"],  # SqNine: 1 of 3 Storm
            "783F761741CEDAD3C854558219366256": ["8367732844E5C853B305D0952E6149CB",   # SqTen: Storm + Sniper of 4 St + 2 Sn
                                                 "9255ACA14859C42E157E888C13674203"],
            "86C5DCEF4527E3157A4E1E9DDF31ECA7": ["E03AB8E34FC8390B25BA1A91A3EE2137",   # SqEleven: both (each has its own
                                                 "2940374D41281BB8DD32B483FD07FC15"],  #   MoveTo / Kill nodes)
            "B199C7E24943A4A67FB5E3B759E17010": ["39AA5A8346F679B346338A880BE1D161",   # Elites: CC + Storm of 2 CC + 2 St
                                                 "42A1F4864E1D4BBF49A95A965786E4A4"],
            "5756FC6D4440384537DD448E78CE8A5F": ("generic", 1),                        # SqOne2: 1 of 3 generic Granit
            "29525D88462F25A0A87B87A3631A928B": ["6006E8DF4D58BE8EF364BCAE70ED4617"],  # Snipers (Gauss): 1 of 5
            "DF1671714F801E893A787DAE82A468E0": ["BA9A8629420055D60C050CA09BBEDFC0"],  # FinalSquad: CC (1 of 1)
        },
        "singles": ["B6A0EEDD400293A089279C8FE831EAB0"],  # CptPrice: one Granit_CloseCombat (Obj spawn)
        "toggles": {
            "NoAmbush": {"default": True, "label": "No ambush",
                         "hover": "On: the elite Granite stand visible in the arena instead of appearing out of "
                                  "nowhere, and the sniper has to spot you before he shoots. Off: as in vanilla.",
                         "nodes": {
                # elites no longer spawn invisible: the hide node shows them instead (its Unhide twin stays as is)
                "E16_MQ01_C03_ToggleNPCHidden_BP_SquadPlaceholder_E16_MQ01_C03_Granit_Elites":
                    {"HideViewType": "EHideViewType::Unhide"},
                # snipers come out of their doors without knowing at once where the player is
                # (IgnoreThreat off too: vanilla pairs ImmediatelyIdentifyEnemy = false with IgnoreThreat = true only
                # on one boss; a sniper that ignores threats and never identifies the player could stay put and stall
                # the stage, which needs the snipers' squad dead)
                "E16_MQ01_C03_SetAIBehavior_SnipersKillPlayer": {"ImmediatelyIdentifyEnemy": "false",
                                                                 "IgnoreThreat": "false"},
            }},
        },
        "nodes": {},
        # b1 PROBE (remove for release): the first Granite (Respawnable CC) at 10% instead of 65%, so the tester can
        # tell which way DamageMultiplier works: his shotgun barely hurts = outgoing (as assumed); he takes ages to
        # kill = it scales damage TAKEN (then this field cannot lower their damage and we need another lever).
        "damage_override": {"9D8254B6458271C223A98DB7AD0B3667": 0.1},
    },
}

# vanilla global variables our node copies may set (the Faust clone controller reads them; every later fight sets its
# own values first: Arch_Bossfight_Faust, the E08 phantom zones)
VANILLA_GLOBALS = {"Faust_Clone_Number", "Faust_Clone_Spawn_Min_Delay", "Faust_Clone_Spawn_Max_Delay"}

NODE_RE = r"^(\S+) : struct\.begin(?: \{bpatch\})?\n(.*?)^struct\.end\n"  # top-level nodes (vanilla or ours)


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        # many vanilla quest files (E15_MQ01, E15_MQ03, every E16_MQ0x) indent with tabs: read them as 3 spaces, the
        # layout every pattern here expects (one tab per level in vanilla)
        return f.read().replace("	", "   ")


def write(rel, text, dry):
    path = os.path.join(OUT, rel.replace("/", os.sep))
    if dry:
        print(f"--- {rel}\n{text}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def actor_patch(guid, body_lines):
    return "\n".join([f"// {TAG}", f"{guid} : struct.begin {{bpatch}}"] + ["   " + l for l in body_lines] + ["struct.end", ""])


# ---- quest node text (3-space indent like E16_MQ01_C03.cfg) -------------------------------------------------------
def all_nodes(qtext):
    # many vanilla files end without a newline after the last struct.end (E08_MQ04_C02's last node is a Faust setter)
    return {m.group(1): m.group(2) for m in re.finditer(NODE_RE, qtext.rstrip("\n") + "\n", re.M | re.S)}


def launchers_lines(groups):
    """groups = [(Excluding, [(SID, Name)])]; [] = vanilla's empty `Launchers =`. Name None = no Name line (vanilla
    writes none on a condition pin's connection, e.g. E14_MQ02_C02's `..._Pin_0` / `_Pin_2`)."""
    if not groups:
        return ["   Launchers ="]
    L = ["   Launchers : struct.begin"]
    for i, (excl, conns) in enumerate(groups):
        L += [f"      [{i}] : struct.begin", f"         Excluding = {excl}", "         Connections : struct.begin"]
        for j, (sid, name) in enumerate(conns):
            L += [f"            [{j}] : struct.begin", f"               SID = {sid}"]
            L += [] if name is None else [f"               Name = {name}".rstrip()]
            L += ["            struct.end"]
        L += ["         struct.end", "      struct.end"]
    return L + ["   struct.end"]


def parse_launchers(body):
    if re.search(r"^   Launchers =\s*$", body, re.M):
        return []
    m = re.search(r"^   Launchers : struct\.begin\n.*?^   struct\.end\n", body, re.M | re.S)
    conn_re = (r"^            \[\d+\] : struct\.begin\n               SID = (\S+)\n"
               r"(?:               Name =[ ]?(.*)\n)?            struct\.end\n")
    groups = [(g.group(1), [(c.group(1), c.group(2)) for c in re.finditer(conn_re, g.group(2), re.M)])
              for g in re.finditer(r"^      \[\d+\] : struct\.begin\n         Excluding = (\w+)\n"
                                   r"         Connections : struct\.begin\n(.*?)^         struct\.end\n      struct\.end\n",
                                   m.group(0), re.M | re.S)]
    if launchers_lines(groups) != m.group(0).rstrip("\n").split("\n"):  # our copy must be exact
        sys.exit("launcher block did not round-trip:\n" + m.group(0))
    return groups


def conns(group):
    """["SID", "SID:Name"] -> [(SID, Name)]"""
    return [tuple(s.split(":", 1)) if ":" in s else (s, "") for s in group]


def out_of(sid, name):
    return [("false", [(sid, name)])]


def node(sid, quest, ntype, groups, fields):
    """A new quest node in vanilla field order: SID, version, quest, type, launchers, then the type's own fields."""
    # (an event node that starts with its quest has no Launchers line at all in vanilla)
    lq = [] if "LaunchOnQuestStart = true" in fields else launchers_lines(groups)
    return ([f"{sid} : struct.begin", f"   SID = {sid}", "   NodePrototypeVersion = 1", f"   QuestSID = {quest}",
             f"   NodeType = EQuestNodeType::{ntype}"] + lq + ["   " + f for f in fields] +
            ["struct.end"])


def gv_condition(var, comparance, value):
    # vanilla GlobalVariable condition (E03_MQ06_If_Spark_VartaShoot, E16_MQ01_C03_If_SkifBranch): one condition in
    # one group, no ConditionCheckType (no vanilla If carries one)
    return ["Conditions : struct.begin", "   [0] : struct.begin", "      [0] : struct.begin",
            "         ConditionType = EQuestConditionType::GlobalVariable",
            f"         ConditionComparance = EConditionComparance::{comparance}",
            f"         GlobalVariablePrototypeSID = {var}", "         ChangeValueMode = EChangeValueMode::Set",
            f"         VariableValue = {value}", "      struct.end", "   struct.end", "struct.end"]


# ---- validation of what we are about to write -------------------------------------------------------------------
def check_structs(rel, text):
    depth = 0
    for n, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.endswith("struct.begin") or "struct.begin {" in s:
            depth += 1
        elif s == "struct.end":
            depth -= 1
            if depth < 0:
                sys.exit(f"{rel}:{n}: struct.end without struct.begin")
    if depth:
        sys.exit(f"{rel}: {depth} struct.begin left open")


def check_quest_patch(rel, text, vanilla_nodes, ifs):
    """Every launcher resolves (vanilla quest or this patch), new SIDs are unique, every If has its consumers.
    Returns the number of new nodes."""
    ours = all_nodes(text)
    if len(ours) != len(re.findall(r"^\S+ : struct\.begin", text, re.M)):
        sys.exit(f"{rel}: duplicate node keys")
    new = {k for k, b in ours.items() if "   NodeType = " in b}
    for k in new:
        if k in vanilla_nodes:
            sys.exit(f"{rel}: new node {k} collides with a vanilla node")
        if f"   SID = {k}\n" not in ours[k]:
            sys.exit(f"{rel}: key {k} and SID differ")
    for k in set(ours) - new:
        if k not in vanilla_nodes:
            sys.exit(f"{rel}: bpatch of {k}, which is not a vanilla node")
    consumers = {}
    for k, b in ours.items():
        for c in re.finditer(r"^               SID = (\S+)\n(?:               Name =[ ]?(.*)$)?", b, re.M):
            sid, name = c.group(1), c.group(2) or ""
            if sid not in vanilla_nodes and sid not in new:
                sys.exit(f"{rel}: {k} is launched by {sid}, which exists nowhere")
            consumers.setdefault((sid, name), []).append(k)
        # conditions on node state (our re-emitted / copied Conditions blocks): a node of ours must exist
        for sid in re.findall(r"^\s+(?:TargetNode|LinkedNodePrototypeSID) = (\S+)$", b, re.M):
            if "_ImmBF" in sid and sid not in new:
                sys.exit(f"{rel}: {k} reads the state of {sid}, which exists nowhere")
    for sid, needs_true in ifs.items():
        if needs_true is None:   # True consumer only
            if not consumers.get((sid, "True")):
                sys.exit(f"{rel}: {sid} has no True consumer")
            continue
        if not consumers.get((sid, "False")):
            sys.exit(f"{rel}: {sid} has no False consumer")
        if needs_true and not consumers.get((sid, "True")):
            sys.exit(f"{rel}: {sid} has no True consumer")
    return len(new)


_ALLQ = {}


def all_quests():
    """every vanilla quest file (to find quest nodes that name a squad member we drop), read once"""
    if not _ALLQ:
        d = os.path.join(GD, "QuestNodePrototypes")
        _ALLQ.update({fn: read(os.path.join(d, fn)) for fn in os.listdir(d) if fn.endswith(".cfg")})
    return _ALLQ


def leaf_only(m, allq):
    """True when every vanilla quest node naming member m is a leaf behaviour node (SetAIBehavior /
    DisableNPCInteraction) that nothing launches from and whose SID is named nowhere else: dropping m then leaves only
    orders aimed at an NPC that never spawned (group A proposal § 5; unverified in game: what such an order does)."""
    for fn, tx in allq.items():
        if m not in tx:
            continue
        for sid, body in re.findall(r"^(\S+) : struct\.begin(.*?)^struct\.end", tx, re.M | re.S):
            if m not in body:
                continue
            nt = re.search(r"NodeType = EQuestNodeType::(\w+)", body)
            if not nt or nt.group(1) not in ("SetAIBehavior", "DisableNPCInteraction"):
                return False
            # named anywhere besides its own key and SID line (a launcher, a Bridge, ...): not a leaf
            name = re.compile(rf"(?<![\w.]){re.escape(sid)}(?![\w.])")
            if any(len(name.findall(tx2)) > (2 if tx2 is tx else 0) for tx2 in allq.values()):
                return False
    return True


def cond_block(sid, body, edits):
    """The node's whole Conditions block (re-emitted as a plain struct inside the bpatch = replaces the list whole,
    every vanilla field kept) with each edit {field: (old, new)} applied to exactly one line. Never a single-index
    bpatch: one replaced a whole list in game before, and a Condition stripped of its type nulls the node."""
    m = re.search(r"^   Conditions : struct\.begin\n.*?^   struct\.end\n", body, re.M | re.S)
    if not m:
        sys.exit(f"{sid}: no Conditions block")
    blk = m.group(0)
    for field, (old, new) in edits.items():
        blk, n = re.subn(rf"^(\s+{field} = ){re.escape(old)}$", lambda mm: mm.group(1) + new, blk, flags=re.M)
        if n != 1:
            sys.exit(f"{sid}: {field} = {old} found {n} times in its Conditions (need exactly 1)")
    return blk.rstrip("\n").split("\n")


def add_setting(mcm, entry):
    """one MCM setting; quest files of one fight that share it must word it the same"""
    for e in mcm:
        if e["key"] == entry["key"]:
            if e != entry:
                sys.exit(f"MCM setting {entry['key']}: entries sharing it disagree:\n{e}\n{entry}")
            return
    if any(e["label"] == entry["label"] for e in mcm):
        sys.exit(f"MCM label {entry['label']!r} used twice")
    mcm.append(entry)


def main():
    dry = "--dry" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    out = {}  # rel path -> text; validated before anything is written
    globals_, setters = [], []  # (var, type, default, values); setter SIDs
    mcm = []  # the MCM settings, in menu order: written to mcm_settings.json for gen_mcm.py and setup_assets.py
    new_nodes = 0
    for quest, b in BATTLES.items():
        if only and quest != only:
            continue
        lvl_dir = os.path.join(GD, SAP, b.get("level", ""))
        qtext = read(os.path.join(GD, "QuestNodePrototypes", quest + ".cfg"))
        vnodes = all_nodes(qtext)
        allq = all_quests()
        total_before = total_after = 0
        written = []
        dropped = []  # (squad, member) in BATTLES order: the members MCM can add back
        for squad, keep in b.get("squads", {}).items():
            vtext = read(os.path.join(lvl_dir, squad + ".cfg"))
            if "SpawnType = ESpawnType::Squad" not in vtext:
                sys.exit(f"{squad}: not a squad")
            if isinstance(keep, tuple):
                # every generic entry counts (TinyGroup: Recon + CC = two entries); entry [0]'s prototype is kept
                total_before += sum(int(n) for n in re.findall(r"SpawnedSquadMembersCount = (\d+)", vtext))
                total_after += keep[1]
                # the list re-emitted whole (plain struct inside the bpatch): a single-index bpatch of a list has
                # replaced the whole list in game before. No DamageMultiplier: squads don't pass one to generic
                # members (vanilla squads never set it and the base default is 0). Generic members have no spawn
                # actor of their own, so MCM cannot add them back.
                proto = re.search(r"SpawnedGenericMembers : struct\.begin.*?SpawnedPrototypeSID = (\S+)", vtext, re.S).group(1)
                body = ["SpawnedGenericMembers : struct.begin",
                        "   [0] : struct.begin",
                        f"      SpawnedSquadMembersCount = {keep[1]}",
                        f"      SpawnedPrototypeSID = {proto}",
                        "   struct.end",
                        "struct.end"]
                out[f"{SAP}/{b['level']}/{squad}/{squad}_patch_{MOD}.cfg"] = actor_patch(squad, body)
                written.append(squad)
                continue
            block = re.search(r"SquadMembersQuestSIDs : struct\.begin(.*?)struct\.end", vtext, re.S).group(1)
            members = re.findall(r"\[\d+\] = ([0-9A-F]{32})", block)
            total_before += len(members)
            total_after += len(keep)
            for k in keep:
                if k not in members:
                    sys.exit(f"{squad}: kept member {k} is not in the vanilla list")
            for m in members:
                if m in keep:
                    continue
                users = [fn for fn, t in allq.items() if m in t]
                if users and not (b.get("leaf_ok") and leaf_only(m, allq)):
                    sys.exit(f"{squad}: dropped member {m} is named by quest nodes in {users}; keep it")
                dropped.append((squad, m))
            body = ["SquadMembersQuestSIDs : struct.begin"]  # plain struct inside the bpatch: replaces the list whole
            body += [f"   [{i}] = {g}" for i, g in enumerate(keep)]
            body += ["struct.end"]
            out[f"{SAP}/{b['level']}/{squad}/{squad}_patch_{MOD}.cfg"] = actor_patch(squad, body)
            written.append(squad)
            for g in keep:
                if "damage" not in b:   # no damage decision for this fight: DamageMultiplier stays vanilla
                    continue
                mt = read(os.path.join(lvl_dir, g + ".cfg"))
                if "SpawnType = ESpawnType::Obj" not in mt or "DamageMultiplier = 1" not in mt:
                    sys.exit(f"{g}: expected an Obj spawn with DamageMultiplier = 1")
                dm = b.get("damage_override", {}).get(g, b["damage"])
                out[f"{SAP}/{b['level']}/{g}/{g}_patch_{MOD}.cfg"] = actor_patch(g, [f"DamageMultiplier = {dm}"])
                written.append(g)
        for g in b.get("singles", []):
            mt = read(os.path.join(lvl_dir, g + ".cfg"))
            if "SpawnType = ESpawnType::Obj" not in mt or "DamageMultiplier = 1" not in mt:
                sys.exit(f"{g}: expected an Obj spawn with DamageMultiplier = 1")
            total_before += 1
            total_after += 1
            out[f"{SAP}/{b['level']}/{g}/{g}_patch_{MOD}.cfg"] = actor_patch(g, [f"DamageMultiplier = {b['damage']}"])
            written.append(g)
        # static spawn actor fields (respawn switches): read when the squad spawns, so not MCM. Merged into the
        # squad's member-list patch when there is one (one patch file per actor).
        for g, fields in b.get("actor_fields", {}).items():
            vt = read(os.path.join(lvl_dir, g + ".cfg"))
            if not re.search(rf"^{g} : struct\.begin\n", vt, re.M) or "SpawnType = ESpawnType::Squad" not in vt:
                sys.exit(f"{g}: not a squad spawn actor of {b['level']}")
            rel = f"{SAP}/{b['level']}/{g}/{g}_patch_{MOD}.cfg"
            for k in fields:
                if not re.search(rf"^   {k} = ", vt, re.M):
                    sys.exit(f"{g}: vanilla actor has no field {k}")
                if rel in out and re.search(rf"^   {k} = ", out[rel], re.M):
                    sys.exit(f"{g}: {k} patched twice")
            body = [f"{k} = {v}" for k, v in fields.items()]
            if rel in out:
                if not out[rel].endswith("\nstruct.end\n"):
                    sys.exit(f"{rel}: cannot merge")
                out[rel] = out[rel][:-len("struct.end\n")] + "".join(f"   {l}\n" for l in body) + "struct.end\n"
            else:
                out[rel] = actor_patch(g, body)
                written.append(g)

        # ---- MCM global variables of this battle (defaults = our defaults: without MCM the mod plays as set here)
        evar = f"ImmBF_{b['mcm']}_Enemies" if "mcm" in b and "enemies_default" in b else None
        if dropped and not evar:
            sys.exit(f"{quest}: members to add back need \"mcm\" and \"enemies_default\"")
        have = {g[0]: g for g in globals_}
        if evar:
            g = (evar, "Int", b["enemies_default"], list(ENEMY_LEVELS))
            if have.get(evar, g) != g:
                sys.exit(f"{evar}: entries sharing it disagree on the default")
            if evar not in have:
                globals_.append(g)
            add_setting(mcm, {"label": f"{b['fight']}: {b.get('enemies_label', 'enemies')}",
                              "hover": b["enemies_hover"] + " Takes effect the next time the fight starts.",
                              "kind": "combo", "labels": list(ENEMY_LEVELS.values()),
                              "default": b["enemies_default"], "category": b["fight"], "var": f"{b['mcm']}Enemies",
                              "key": evar[len("ImmBF_"):], "values": list(ENEMY_LEVELS)})
        if "mcm" in b:
            for name, t in b.get("toggles", {}).items():
                var = f"ImmBF_{b['mcm']}_{name}"
                g = (var, "Bool", t["default"], [True, False])
                if have.get(var, g) != g:
                    sys.exit(f"{var}: entries sharing it disagree on the default")
                if var not in have:
                    globals_.append(g)
                add_setting(mcm, {"label": f"{b['fight']}: {t['label'][0].lower() + t['label'][1:]}",
                                  "hover": t["hover"] + " Takes effect the next time the fight starts.", "kind": "bool",
                                  "default": t["default"], "category": b["fight"], "var": f"{b['mcm']}{name}",
                                  "key": var[len("ImmBF_"):], "values": [True, False]})
        elif b.get("toggles"):
            sys.exit(f"{quest}: toggles need an \"mcm\" name")

        # ---- quest patch. chunks = the nodes in output order; a vanilla node patched by several features (relaunch
        # + a condition value) gets one bpatch with all of them (two nodes with one key would be a duplicate)
        chunks = []
        bpatched = {}  # vanilla SID -> (its chunk, the top-level fields it sets)

        def bpatch(sid, body, fields):
            if sid not in vnodes:
                sys.exit(f"{quest}: node {sid} not found")
            if sid in bpatched:
                ch, have_f = bpatched[sid]
                if have_f & fields:
                    sys.exit(f"{sid}: {sorted(have_f & fields)} patched twice")
                ch[-1:-1] = body
                have_f |= fields
            else:
                ch = [f"{sid} : struct.begin {{bpatch}}"] + body + ["struct.end"]
                chunks.append(ch)
                bpatched[sid] = (ch, set(fields))

        # plain node patches (vanilla nodes, bpatch)
        for sid, fields in b.get("nodes", {}).items():
            if sid not in vnodes:
                sys.exit(f"{quest}: node {sid} not found")
            for k in fields:
                if not re.search(rf"^\s*{k} = ", vnodes[sid], re.M):
                    sys.exit(f"{sid}: vanilla node has no field {k}")
            bpatch(sid, [f"   {k} = {v}" for k, v in fields.items()], set(fields))
        for sid, groups in b.get("relaunch", {}).items():
            bpatch(sid, launchers_lines([("false", conns(g)) for g in groups]), {"Launchers"})
        # extra launchers: the vanilla node keeps its own groups exactly and gets ours appended
        for sid, groups in b.get("extra_launchers", {}).items():
            if sid not in vnodes:
                sys.exit(f"{quest}: node {sid} not found")
            bpatch(sid, launchers_lines(parse_launchers(vnodes[sid]) + [("false", conns(g)) for g in groups]), {"Launchers"})
        # conditions re-emitted with one value swapped: retarget (TargetNode old -> new) and cond_values
        retarget = b.get("retarget", {})
        cedits = {}
        for sid, (old, new) in retarget.items():
            cedits.setdefault(sid, {})["TargetNode"] = (old, new)
        for sid, fv in b.get("cond_values", {}).items():
            for k, v in fv.items():
                if k in cedits.get(sid, {}):
                    sys.exit(f"{sid}: {k} edited twice")
                cedits.setdefault(sid, {})[k] = v
        for sid, edits in cedits.items():
            if sid not in vnodes:
                sys.exit(f"{quest}: node {sid} not found")
            bpatch(sid, cond_block(sid, vnodes[sid], edits), {"Conditions"})
        ifs = {}  # our If SID -> needs a True consumer (None: True only)
        for suffix, ntype, groups, fields in b.get("add", []):
            if isinstance(fields, tuple) and fields[0] == "toggle":   # an If on that MCM toggle (missing variable = True)
                if fields[1] not in b.get("toggles", {}):
                    sys.exit(f"{quest}: add {suffix}: no toggle {fields[1]}")
                fields = gv_condition(f"ImmBF_{b['mcm']}_{fields[1]}", "Equal", "true")
                ifs[f"{quest}_ImmBF_{suffix}"] = None   # True consumer only (False = the vanilla way: nothing)
            elif isinstance(fields, tuple) and fields[0] == "enemies":   # an If on the Enemies variable
                if not evar:
                    sys.exit(f"{quest}: add {suffix}: the battle has no Enemies variable")
                fields = gv_condition(evar, fields[1], fields[2])
                ifs[f"{quest}_ImmBF_{suffix}"] = True   # both outputs used
            elif isinstance(fields, tuple):
                sys.exit(f"{quest}: add {suffix}: unknown condition {fields}")
            chunks.append(node(f"{quest}_ImmBF_{suffix}", quest, ntype, [("false", conns(g)) for g in groups], fields))
        pre = f"{quest}_ImmBF_"

        # ---- enemies added back: per squad and tier an If launched like the squad's own Spawn node (never off the
        # Spawn's output: cfg-reference.md). On False it spawns each member's own Obj spawn actor and adds it to its
        # vanilla squad, so the squad's death event waits for it. Both from the same launcher, no delay: vanilla
        # E07_DugaAssault_C01 adds 54 single spawns to squads exactly this way (saves 16 delay nodes).
        tiers = {}  # (squad, tier) -> [members]
        for i, (squad, m) in enumerate(dropped):
            tiers.setdefault((squad, 1 + i % 2), []).append(m)  # alternate, so "Fewer" gets about half
        counts = {lvl: total_after for lvl in ENEMY_LEVELS}
        for (squad, tier), members in tiers.items():
            spawns = [s for s, nb in vnodes.items()
                      if "   NodeType = EQuestNodeType::Spawn\n" in nb and f"   TargetQuestGuid = {squad}\n" in nb]
            if not spawns:
                sys.exit(f"{quest}: no Spawn node for squad {squad}")
            groups = []
            excl = []
            for s in spawns:  # several Spawn nodes for one squad: the If takes every launcher group (it runs once)
                for g in parse_launchers(vnodes[s]):
                    # an Excluding group despawns what the node spawned: it goes on our member Spawns, not on the If
                    (excl if g[0] == "true" else groups).append(g)
            copy = {}
            for f in ("IgnoreDamageType", "SpawnHidden", "SpawnNodeExcludeType"):
                vals = {re.search(rf"^   {f} = (\S+)$", vnodes[s], re.M).group(1) for s in spawns}
                if len(vals) != 1:
                    sys.exit(f"{quest}: Spawn nodes of {squad} disagree on {f}: {vals}")
                copy[f] = vals.pop()
            # SID part after SpawnObjectNPCMonster_ (E15_MQ03 names its Spawn nodes SpawnNPC_...: then minus the quest)
            short = (spawns[0].split("SpawnObjectNPCMonster_")[-1] if "SpawnObjectNPCMonster_" in spawns[0]
                     else spawns[0][len(quest) + 1:])
            if_sid = f"{pre}If_Enemies_{short}_{tier}"
            ifs[if_sid] = False
            chunks.append(node(if_sid, quest, "If", groups, gv_condition(evar, "Less", tier)))
            for m in members:
                mt = read(os.path.join(lvl_dir, m + ".cfg"))
                if "SpawnType = ESpawnType::Obj" not in mt or not all(f"Position{a} = " in mt for a in "XYZ"):
                    sys.exit(f"{m}: expected an Obj spawn with a position")
                if "DamageMultiplier = 1" not in mt:
                    sys.exit(f"{m}: expected DamageMultiplier = 1")
                chunks.append(node(f"{pre}Spawn_{m}", quest, "Spawn", out_of(if_sid, "False") + excl,
                                   [f"TargetQuestGuid = {m}"] + [f"{k} = {v}" for k, v in copy.items()]))
                chunks.append(node(f"{pre}AddToSquad_{m}", quest, "AddOrRemoveFromSquad", out_of(if_sid, "False"),
                                   [f"TargetQuestGuid = {m}", f"Squad = {squad}", "Remove = false"]))
                # the same damage as the kept members (unused while MCM stays on "Much fewer")
                if "damage" in b:
                    out[f"{SAP}/{b['level']}/{m}/{m}_patch_{MOD}.cfg"] = actor_patch(m, [f"DamageMultiplier = {b['damage']}"])
                    written.append(m)
                for lvl in ENEMY_LEVELS:
                    counts[lvl] += lvl >= tier
        if "counts" in b:   # levels that are not member add-backs (Boundary: whole waves)
            counts = b["counts"]
            total_before = counts[max(ENEMY_LEVELS)]

        # ---- toggles: an If launched like the vanilla node; True -> our changed copy (<SID>_ImmBF), False -> the
        # vanilla node, whose launchers become only that output (a plain Launchers struct inside the bpatch replaces
        # the list whole; every other field stays vanilla)
        # One If per toggle and launcher set: toggled nodes started by the same launchers share it. Excluding launcher
        # groups (they undo / despawn the node) stay on the vanilla node and go on the copy too, never on the If.
        # consumers_vanilla_only: toggled nodes whose consumers may run on the vanilla (False) path only.
        # Conditions reading the node's state are allowed when "retarget" points them at the toggle's If.
        n_if = 0
        shared = {}  # (toggle, starting groups) -> If SID
        for name, t in b.get("toggles", {}).items():
            var = f"ImmBF_{b['mcm']}_{name}"
            for sid, fields in t["nodes"].items():
                if sid not in vnodes:
                    sys.exit(f"{quest}: node {sid} not found")
                body = vnodes[sid]
                # a node launched by this one, or a Bridge condition on it, would miss our copy
                ref = re.compile(rf"= {re.escape(sid)}$", re.M)
                users = [k for k, nb in vnodes.items() if k != sid and ref.search(nb)]
                if sid in t.get("consumers_vanilla_only", []):
                    users = []
                # retargeted readers: fine if nothing outside their Conditions block names the node
                users = [k for k in users if not (retarget.get(k, (None,))[0] == sid and not ref.search(
                    re.sub(r"^   Conditions : struct\.begin\n.*?^   struct\.end\n", "", vnodes[k], flags=re.M | re.S)))]
                users += [fn for fn, tx in allq.items() if fn != quest + ".cfg" and sid in tx]
                if users:
                    sys.exit(f"{sid}: used by {users}; add our copy's SID to them before toggling it")
                groups = parse_launchers(body)
                start = [g for g in groups if g[0] != "true"]
                excl = [g for g in groups if g[0] == "true"]
                key = (name, repr(start))
                if key not in shared:
                    n_if += 1
                    shared[key] = f"{pre}If_{name}_{n_if}"
                    ifs[shared[key]] = False
                    chunks.append(node(shared[key], quest, "If", start, gv_condition(var, "Equal", "true")))
                if_sid = shared[key]
                bpatch(sid, launchers_lines(out_of(if_sid, "False") + excl), {"Launchers"})
                if fields is None:   # switched off when the toggle is on: no copy, nothing on True
                    continue
                ifs[if_sid] = True
                cbody = body.replace(f"   SID = {sid}\n", f"   SID = {sid}_ImmBF\n", 1)
                cbody = re.sub(r"^   Launchers : struct\.begin\n.*?^   struct\.end\n",
                               lambda _: "\n".join(launchers_lines(out_of(if_sid, "True") + excl)) + "\n",
                               cbody, count=1, flags=re.M | re.S)
                for k, v in fields.items():
                    cbody, n = re.subn(rf"^   {k} = .*$", f"   {k} = {v}", cbody, count=1, flags=re.M)
                    if not n:
                        sys.exit(f"{sid}: vanilla node has no field {k}")
                chunks.append([f"{sid}_ImmBF : struct.begin"] + cbody.rstrip("\n").split("\n") + ["struct.end"])
        # a retarget must name the toggle If that runs exactly when the vanilla node would (same starting launchers)
        starts = {s: st for (nm, st), s in shared.items()}
        for k, (old, new) in retarget.items():
            if new not in starts or starts[new] != repr([g for g in parse_launchers(vnodes[old]) if g[0] != "true"]):
                sys.exit(f"{k}: retarget {new} is not a toggle If launched like {old}")
        n_new = 0
        rel = f"QuestNodePrototypes/{quest}/{quest}_patch_{MOD}.cfg"
        if chunks:   # an entry of spawn actor data only (Korshunov) writes no quest patch
            out[rel] = "\n".join([f"// {TAG}"] + [l for ch in chunks for l in ch]) + "\n"
            n_new = check_quest_patch(rel, out[rel], vnodes, ifs)
        new_nodes += n_new
        print(f"{quest}: {total_before} vanilla -> "
              + " / ".join(f"{counts[l]} {ENEMY_LEVELS[l].lower()}" for l in ENEMY_LEVELS)
              + f" enemies ({len(dropped)} named members can come back, generic ones cannot); "
              + f"{len(written)} actor patches, {len(b.get('nodes', {}))} plain node patches, "
              + f"{len(b.get('relaunch', {}))} relaunched, {len(cedits)} conditions re-emitted, "
              + f"{len(b.get('toggles', {}))} toggles, {n_new} new quest nodes")
        for (squad, tier), members in tiers.items():
            print(f"   tier {tier} ({ENEMY_LEVELS[tier]}): squad {squad} + {', '.join(members)}")

    if only:   # no MCM files: write just this battle's
        for rel, text in out.items():
            check_structs(rel, text)
            write(rel, text, dry)
        print(f"{len(out)} files (--only {only})")
        return
    # ---- global variables: refkey [0] like vanilla's named entries. No ID: only vanilla's first 22 indexed entries
    # carry one; the ~300 named ones (Faust_Clone_Number ...) inherit [0]'s ID = 0, so ID is no key.
    gl = [f"// {TAG}"]
    for var, typ, default, _ in globals_:
        dv = ("True" if default else "False") if typ == "Bool" else default  # vanilla DefaultValue: True / False
        gl += [f"{var} : struct.begin {{refkey=[0]}}", f"   SID = {var}", f"   Type = EGlobalVariableType::{typ}",
               f"   DefaultValue = {dv}", "struct.end"]
    out[f"GlobalVariablePrototypes/GlobalVariablePrototypes_patch_{MOD}.cfg"] = "\n".join(gl) + "\n"
    vglobals = read(os.path.join(GD, "GlobalVariablePrototypes.cfg"))
    for var, *_ in globals_:
        if re.search(rf"^{var} : |SID = {var}$", vglobals, re.M):
            sys.exit(f"{var}: already a vanilla global variable")

    # ---- setters for MCM in rootgraph (always running). No launchers: the MCM provider starts them by SID,
    # "ImmBF_Set_" + key + "_" + value, key = the variable minus "ImmBF_", bools as true / false.
    rg = [f"// {TAG}"]
    for var, typ, _, values in globals_:
        for v in values:
            vs = ("true" if v else "false") if typ == "Bool" else str(v)  # vanilla VariableValue: lowercase bools
            sid = f"ImmBF_Set_{var[len('ImmBF_'):]}_{vs}"
            setters.append(sid)
            # field layout of vanilla E07_MQ05_SetGlobalVariable_Faust_Clone_Number
            rg += node(sid, "rootgraph", "SetGlobalVariable", [],
                       [f"GlobalVariablePrototypeSID = {var}", "ChangeValueMode = EChangeValueMode::Set",
                        f"VariableValue = {vs}"])
    rel = f"QuestNodePrototypes/rootgraph/rootgraph_patch_{MOD}.cfg"
    out[rel] = "\n".join(rg) + "\n"
    new_nodes += check_quest_patch(rel, out[rel], all_nodes(read(os.path.join(GD, "QuestNodePrototypes", "rootgraph.cfg"))), {})

    gvars = {g[0] for g in globals_}
    for rel, text in out.items():
        check_structs(rel, text)
        for var in re.findall(r"GlobalVariablePrototypeSID = (\S+)", text):
            if var not in gvars and var not in VANILLA_GLOBALS:
                sys.exit(f"{rel}: global variable {var} is not ours")
    for rel, text in out.items():
        write(rel, text, dry)
    if True:   # repo tooling (gen_mcm.py, setup_assets.py), also on --dry
        json.dump(mcm, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcm_settings.json"), "w",
                            encoding="utf-8"), indent=1)
    print(f"{len(out)} files, {new_nodes} new quest nodes in total, {len(mcm)} MCM settings")
    print("globals: " + ", ".join(f"{v} ({t}, default {d})" for v, t, d, _ in globals_))
    print("setters: " + ", ".join(setters))


if __name__ == "__main__":
    main()
