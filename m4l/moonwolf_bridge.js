// Moonwolf Bridge — M4L LiveAPI bridge for Moonwolf Layers game
// Receives commands via UDP port 8002, executes LiveAPI calls
// Extends CoLaB's /live/ command set with session setup capabilities
//
// Load this device on any track in Ableton. It listens on port 8002.
// The game sends plain text commands like:
//   /moonwolf/setup/song 92 3          — set tempo, create 3 tracks
//   /moonwolf/track/create drums 9     — create track named "drums" on ch 10
//   /moonwolf/track/arm 0              — arm track 0
//   /moonwolf/transport/play           — start playing
//   /moonwolf/transport/record         — session record
//   /moonwolf/clip/fire 0 0            — fire clip at track 0, slot 0

var inlets = 1;
var outlets = 1;

var MOONWOLF_PORT = 8002;

function init() {
    post("Moonwolf Bridge v1.0 — LiveAPI controller for Moonwolf Layers\n");
    post("Listening on UDP port " + MOONWOLF_PORT + "\n");
    post("Commands: /moonwolf/setup/*, /moonwolf/track/*, /moonwolf/transport/*, /moonwolf/clip/*\n");
}

function incoming(msg) {
    // Called when UDP message arrives (via [udpreceive 8002] → [prepend incoming] → [js])
    var str = msg.toString().replace("incoming ", "");
    handleCommand(str);
}

function anything() {
    // Handle messages from Max patcher
    var args = arrayfromargs(messagename, arguments);
    var str = args.join(" ");
    if (str.indexOf("incoming ") === 0) {
        str = str.replace("incoming ", "");
    }
    handleCommand(str);
}

function handleCommand(msg) {
    var parts = msg.trim().split(" ");
    var cmd = parts[0];
    var args = parts.slice(1);

    try {
        // ===== TRANSPORT =====
        if (cmd === "/moonwolf/transport/play") {
            var ls = new LiveAPI("live_set");
            ls.call("start_playing");
            post("  >> PLAY\n");
        }
        else if (cmd === "/moonwolf/transport/stop") {
            var ls = new LiveAPI("live_set");
            ls.call("stop_playing");
            post("  >> STOP\n");
        }
        else if (cmd === "/moonwolf/transport/record") {
            var ls = new LiveAPI("live_set");
            ls.set("session_record", 1);
            post("  >> SESSION RECORD ON\n");
        }
        else if (cmd === "/moonwolf/transport/stop_record") {
            var ls = new LiveAPI("live_set");
            ls.set("session_record", 0);
            post("  >> SESSION RECORD OFF\n");
        }
        else if (cmd === "/moonwolf/transport/tempo" && args.length >= 1) {
            var ls = new LiveAPI("live_set");
            ls.set("tempo", parseFloat(args[0]));
            post("  >> TEMPO " + args[0] + " BPM\n");
        }
        else if (cmd === "/moonwolf/transport/metronome") {
            var ls = new LiveAPI("live_set");
            var val = args.length >= 1 ? parseInt(args[0]) : 1;
            ls.set("metronome", val);
            post("  >> METRONOME " + (val ? "ON" : "OFF") + "\n");
        }

        // ===== SONG SETUP =====
        else if (cmd === "/moonwolf/setup/song" && args.length >= 1) {
            // /moonwolf/setup/song <bpm> [num_tracks]
            var bpm = parseFloat(args[0]);
            var numTracks = args.length >= 2 ? parseInt(args[1]) : 0;

            var ls = new LiveAPI("live_set");
            ls.set("tempo", bpm);
            ls.call("stop_playing");
            ls.set("session_record", 0);

            // Create requested tracks
            for (var i = 0; i < numTracks; i++) {
                ls.call("create_midi_track", -1); // -1 = append at end
            }

            post("  >> SETUP: " + bpm + " BPM, " + numTracks + " new tracks\n");
        }

        // ===== TRACK MANAGEMENT =====
        else if (cmd === "/moonwolf/track/create" && args.length >= 1) {
            // /moonwolf/track/create <name> [midi_channel]
            var name = args[0];
            var ch = args.length >= 2 ? parseInt(args[1]) : 0;

            var ls = new LiveAPI("live_set");
            var trackCount = ls.getcount("tracks");
            ls.call("create_midi_track", -1); // Append

            // Name the new track
            var newTrack = new LiveAPI("live_set tracks " + trackCount);
            newTrack.set("name", name);

            // Set MIDI input routing to "LoopBe Internal MIDI" or first available
            // Note: input_routing_type takes a dict with 'display_name' key
            // The exact routing depends on available MIDI inputs in the session

            post("  >> CREATED TRACK '" + name + "' (ch." + (ch + 1) + ") at index " + trackCount + "\n");
        }
        else if (cmd === "/moonwolf/track/arm" && args.length >= 1) {
            var trackIdx = parseInt(args[0]);
            var armed = args.length >= 2 ? parseInt(args[1]) : 1;
            var t = new LiveAPI("live_set tracks " + trackIdx);
            t.set("arm", armed);
            post("  >> ARM TRACK " + trackIdx + " = " + armed + "\n");
        }
        else if (cmd === "/moonwolf/track/name" && args.length >= 2) {
            var trackIdx = parseInt(args[0]);
            var name = args.slice(1).join(" ");
            var t = new LiveAPI("live_set tracks " + trackIdx);
            t.set("name", name);
            post("  >> NAME TRACK " + trackIdx + " = '" + name + "'\n");
        }
        else if (cmd === "/moonwolf/track/mute" && args.length >= 1) {
            var trackIdx = parseInt(args[0]);
            var muted = args.length >= 2 ? parseInt(args[1]) : 1;
            var t = new LiveAPI("live_set tracks " + trackIdx);
            t.set("mute", muted);
            post("  >> MUTE TRACK " + trackIdx + " = " + muted + "\n");
        }
        else if (cmd === "/moonwolf/track/solo" && args.length >= 1) {
            var trackIdx = parseInt(args[0]);
            var solo = args.length >= 2 ? parseInt(args[1]) : 1;
            var t = new LiveAPI("live_set tracks " + trackIdx);
            t.set("solo", solo);
            post("  >> SOLO TRACK " + trackIdx + " = " + solo + "\n");
        }
        else if (cmd === "/moonwolf/track/volume" && args.length >= 2) {
            var trackIdx = parseInt(args[0]);
            var vol = parseFloat(args[1]);
            var mixer = new LiveAPI("live_set tracks " + trackIdx + " mixer_device volume");
            mixer.set("value", vol);
            post("  >> VOLUME TRACK " + trackIdx + " = " + vol + "\n");
        }
        else if (cmd === "/moonwolf/track/delete" && args.length >= 1) {
            var trackIdx = parseInt(args[0]);
            var ls = new LiveAPI("live_set");
            ls.call("delete_track", trackIdx);
            post("  >> DELETE TRACK " + trackIdx + "\n");
        }

        // ===== CLIP CONTROL =====
        else if (cmd === "/moonwolf/clip/fire" && args.length >= 2) {
            var track = parseInt(args[0]);
            var slot = parseInt(args[1]);
            var clip = new LiveAPI("live_set tracks " + track + " clip_slots " + slot + " clip");
            clip.call("fire");
            post("  >> FIRE CLIP " + track + "/" + slot + "\n");
        }
        else if (cmd === "/moonwolf/clip/stop" && args.length >= 1) {
            var track = parseInt(args[0]);
            var t = new LiveAPI("live_set tracks " + track);
            t.call("stop_all_clips");
            post("  >> STOP CLIPS track " + track + "\n");
        }
        else if (cmd === "/moonwolf/clip/quantize" && args.length >= 2) {
            var track = parseInt(args[0]);
            var slot = parseInt(args[1]);
            var grid = args.length >= 3 ? parseInt(args[2]) : 5; // 5 = 1/16
            var clip = new LiveAPI("live_set tracks " + track + " clip_slots " + slot + " clip");
            clip.call("quantize", grid, 1.0);
            post("  >> QUANTIZE CLIP " + track + "/" + slot + " grid=" + grid + "\n");
        }
        else if (cmd === "/moonwolf/clip/loop" && args.length >= 2) {
            var track = parseInt(args[0]);
            var slot = parseInt(args[1]);
            var looping = args.length >= 3 ? parseInt(args[2]) : 1;
            var clip = new LiveAPI("live_set tracks " + track + " clip_slots " + slot + " clip");
            clip.set("looping", looping);
            post("  >> LOOP CLIP " + track + "/" + slot + " = " + looping + "\n");
        }

        // ===== DEVICE LOADING =====
        else if (cmd === "/moonwolf/device/load" && args.length >= 2) {
            // /moonwolf/device/load <track> <device_name>
            // Loads a device by browser path or name onto a track
            var trackIdx = parseInt(args[0]);
            var deviceName = args.slice(1).join(" ");
            // Use the browser to load — this requires the device to be in the user library
            // For built-in devices, we can use create_device with a URI
            post("  >> LOAD DEVICE '" + deviceName + "' on track " + trackIdx + "\n");
            post("  NOTE: Device loading requires dragging from browser or using specific URIs\n");
        }

        // ===== QUERY =====
        else if (cmd === "/moonwolf/query/tracks") {
            var ls = new LiveAPI("live_set");
            var count = ls.getcount("tracks");
            post("  >> TRACKS: " + count + "\n");
            for (var i = 0; i < count; i++) {
                var t = new LiveAPI("live_set tracks " + i);
                var name = t.get("name");
                var armed = t.get("arm");
                var muted = t.get("mute");
                post("    [" + i + "] " + name + (armed == 1 ? " [ARMED]" : "") + (muted == 1 ? " [MUTED]" : "") + "\n");
            }
            outlet(0, "tracks " + count);
        }
        else if (cmd === "/moonwolf/query/tempo") {
            var ls = new LiveAPI("live_set");
            var tempo = ls.get("tempo");
            post("  >> TEMPO: " + tempo + " BPM\n");
            outlet(0, "tempo " + tempo);
        }
        else if (cmd === "/moonwolf/query/playing") {
            var ls = new LiveAPI("live_set");
            var playing = ls.get("is_playing");
            post("  >> PLAYING: " + playing + "\n");
            outlet(0, "playing " + playing);
        }

        // ===== ARM ALL / DISARM ALL =====
        else if (cmd === "/moonwolf/arm_all") {
            var ls = new LiveAPI("live_set");
            var count = ls.getcount("tracks");
            for (var i = 0; i < count; i++) {
                var t = new LiveAPI("live_set tracks " + i);
                t.set("arm", 0); // Disarm all first
            }
            // Then arm the specified one
            if (args.length >= 1) {
                var armIdx = parseInt(args[0]);
                var t2 = new LiveAPI("live_set tracks " + armIdx);
                t2.set("arm", 1);
                post("  >> ARMED track " + armIdx + " (all others disarmed)\n");
            } else {
                post("  >> ALL TRACKS DISARMED\n");
            }
        }

        // ===== FULL SESSION SETUP FOR MOONWOLF =====
        else if (cmd === "/moonwolf/setup/session" && args.length >= 1) {
            // /moonwolf/setup/session <bpm> <json_layers>
            // Example: /moonwolf/setup/session 92 drums:9,bass:2,guitar:1
            var bpm = parseFloat(args[0]);
            var ls = new LiveAPI("live_set");

            // Set tempo
            ls.set("tempo", bpm);
            ls.call("stop_playing");
            ls.set("session_record", 0);

            // Parse layers
            if (args.length >= 2) {
                var layerDefs = args[1].split(",");
                for (var i = 0; i < layerDefs.length; i++) {
                    var parts2 = layerDefs[i].split(":");
                    var layerName = parts2[0];
                    var ch = parts2.length > 1 ? parseInt(parts2[1]) : 0;

                    // Create track
                    var countBefore = ls.getcount("tracks");
                    ls.call("create_midi_track", -1);
                    var newIdx = countBefore;

                    // Name it
                    var nt = new LiveAPI("live_set tracks " + newIdx);
                    nt.set("name", "MW: " + layerName);

                    post("  >> Created 'MW: " + layerName + "' (ch." + (ch + 1) + ") at idx " + newIdx + "\n");
                }
            }

            // Arm first track
            var total = ls.getcount("tracks");
            if (total > 0) {
                var first = new LiveAPI("live_set tracks " + (total - layerDefs.length));
                first.set("arm", 1);
            }

            post("  >> SESSION READY: " + bpm + " BPM, " + (args.length >= 2 ? layerDefs.length : 0) + " layers\n");
        }

        else {
            post("  ?? Unknown command: " + cmd + "\n");
        }

    } catch(e) {
        post("  !! ERROR: " + e.message + " (cmd: " + cmd + ")\n");
    }
}

// Auto-init
init();
