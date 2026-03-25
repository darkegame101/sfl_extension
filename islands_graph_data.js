// islands_graph_data.js
// Tài liệu quản lý đồ thị cho toàn bộ đảo SFL
// Chỉnh sửa tọa độ {x, y} tại đây để bot di chuyển chính xác

const ISLAND_GRAPHS = {
    "plaza": {
        nodes: {
            "root": { "x": 427, "y": 448 },
            "pete-ps": { "x": 389, "y": 425 },
            "st-peggy": { "x": 203, "y": 445 },
            "peggy-ps": { "x": 203, "y": 392 },
            "bridge": { "x": 59, "y": 443 },
            "root2": { "x": 59, "y": 308 },
            "Tywin-ps": { "x": 64, "y": 84 },
            "midle tvs": { "x": 209, "y": 83 },
            "raven-ps": { "x": 281, "y": 83 },
            "midel-tvs2": { "x": 213, "y": 174 },
            "blacksmith-ps": { "x": 365, "y": 139 },
            "midle-blacsmith": { "x": 365, "y": 186 },
            "hayor": { "x": 436, "y": 186 },
            "center top": { "x": 432, "y": 281 },
            "center bottom": { "x": 431, "y": 340 },
            "ct top-left": { "x": 406, "y": 281 },
            "ct bottom-left": { "x": 401, "y": 340 },
            "ct top-right": { "x": 467, "y": 291 },
            "ct bottom-right": { "x": 467, "y": 340 },
            "midle-betty1": { "x": 497, "y": 186 },
            "cornwell-ps": { "x": 497, "y": 126 },
            "betty-ps": { "x": 529, "y": 122 },
            "timmy-ps": { "x": 627, "y": 122 },
            "bert-ps": { "x": 776, "y": 122 },
            "midle grim": { "x": 467, "y": 312 },
            "midle grim 2": { "x": 783, "y": 312 },
            "grim-ps": { "x": 783, "y": 370 }
        },
        edges: [
            ["root", "pete-ps"],
            ["root", "center bottom"],
            ["root", "st-peggy"],
            ["st-peggy", "peggy-ps"],
            ["st-peggy", "bridge"],
            ["bridge", "root2"],
            ["root2", "Tywin-ps"],
            ["Tywin-ps", "midle tvs"],
            ["midle tvs", "raven-ps"],
            ["midle tvs", "midel-tvs2"],
            ["midel-tvs2", "blacksmith-ps"],
            ["blacksmith-ps", "midle-blacsmith"],
            ["midle-blacsmith", "hayor"],
            ["hayor", "center top"],
            ["center top", "center bottom"],
            ["center top", "ct top-left"],
            ["center top", "ct top-right"],
            ["ct top-left", "ct bottom-left"],
            ["ct bottom-left", "center bottom"],
            ["ct top-right", "midle-betty1"],
            ["midle-betty1", "cornwell-ps"],
            ["cornwell-ps", "betty-ps"],
            ["betty-ps", "timmy-ps"],
            ["timmy-ps", "bert-ps"],
            ["ct top-right", "midle grim"],
            ["midle grim", "ct bottom-right"],
            ["midle grim", "midle grim 2"],
            ["midle grim 2", "grim-ps"],
            ["ct bottom-right", "center bottom"]
        ]
    },
    "beach": {
        nodes: {
            "center":     { x:    0,  y:    0 },
            "west":       { x: -200,  y:    0 },
            "west2":      { x: -400,  y:    0 },
            "east":       { x:  200,  y:    0 },
            "north":      { x:    0,  y: -200 },
            "south":      { x:    0,  y:  200 },
            "corale":     { x: -350,  y:  120 },
            "old_salty":  { x: -400,  y:    0 },
            "pharaoh_n":  { x: -400,  y: -200 },
            "pharaoh":    { x: -500,  y: -300 },
            "finn":       { x:  250,  y:  -80 },
            "tango":      { x:  488,  y:  411 },
            "tango_path": { x:  300,  y:  300 },
        },
        edges: [
            ["center",     "west"],
            ["west",       "west2"],
            ["west2",      "old_salty"],
            ["west2",      "corale"],
            ["west2",      "pharaoh_n"],
            ["pharaoh_n",  "pharaoh"],
            ["center",     "east"],
            ["east",       "finn"],
            ["center",     "north"],
            ["center",     "south"],
            ["south",      "tango_path"],
            ["tango_path", "tango"],
        ]
    },
    "kingdom": {
        nodes: {
            "center":    { x:    0,  y:    0 },
            "north":     { x:    0,  y: -200 },
            "south":     { x:    0,  y:  200 },
            "east":      { x:  200,  y:    0 },
            "gambit":    { x:  250,  y:  150 },
            "jester":    { x:  100,  y:    0 },
            "victoria":  { x:    0,  y: -300 },
        },
        edges: [
            ["center",   "north"],
            ["center",   "south"],
            ["center",   "east"],
            ["east",     "gambit"],
            ["center",   "jester"],
            ["north",    "victoria"],
        ]
    },
    "retreat": {
        nodes: {
            "root": { "x": 429, "y": 443 },
            "midle0": { "x": 319, "y": 294 },
            "midle 1": { "x": 369, "y": 294 },
            "midel2": { "x": 369, "y": 246 },
            "guria and grubunk -ps": { "x": 409, "y": 246 },
            "gordo midle": { "x": 409, "y": 260 },
            "gordo-ps": { "x": 552, "y": 260 }
        },
        edges: [
            ["root", "midle0"],
            ["midle0", "midle 1"],
            ["midle 1", "midel2"],
            ["midel2", "guria and grubunk -ps"],
            ["guria and grubunk -ps", "gordo midle"],
            ["midle 1", "gordo midle"],
            ["gordo midle", "gordo-ps"]
        ]
    }
};

window.SFL_ISLAND_GRAPHS = ISLAND_GRAPHS;
