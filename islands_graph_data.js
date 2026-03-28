// islands_graph_data.js
// Tài liệu quản lý đồ thị cho toàn bộ đảo SFL
// Chỉnh sửa tọa độ {x, y} tại đây để bot di chuyển chính xác

const ISLAND_GRAPHS = {
    "plaza": {
        nodes: {
            "root": { "x": 427, "y": 448 },
            "pete-ps": { "x": 389, "y": 425 },
            "st-peggy": { "x": 203, "y": 454 },
            "peggy-ps": { "x": 203, "y": 392 },
            "bridge": { "x": 59, "y": 443 },
            "root2": { "x": 59, "y": 308 },
            "Tywin-ps": { "x": 64, "y": 84 },
            "midle tvs": { "x": 209, "y": 83 },
            "raven-ps": { "x": 281, "y": 83 },
            "midel-tvs2": { "x": 213, "y": 174 },
            "blacksmith-ps": { "x": 368, "y": 139 },
            "midle-blacsmith": { "x": 368, "y": 194 },
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
            ["center top", "ct top-left"],
            ["center top", "ct top-right"],
            ["ct top-left", "ct bottom-left"],
            ["ct bottom-left", "center bottom"],
            ["midle-betty1", "cornwell-ps"],
            ["cornwell-ps", "betty-ps"],
            ["betty-ps", "timmy-ps"],
            ["timmy-ps", "bert-ps"],
            ["ct top-right", "midle grim"],
            ["midle grim", "ct bottom-right"],
            ["midle grim", "midle grim 2"],
            ["midle grim 2", "grim-ps"],
            ["ct bottom-right", "center bottom"],
            ["midle-betty1", "hayor"]
        ]
    },
    "beach": {
        nodes: {
            "root": { x: 527, y: 711 },
            "corale midle": { x: 363, y: 711 },
            "corale-ps": { x: 244, y: 711 },
            "tanggo midle 1": { x: 376, y: 518 },
            "tanggo midle 2": { x: 475, y: 518 },
            "tanggo-ps": { x: 475, y: 423 },
            "old salty midle": { x: 386, y: 242 },
            "old salty midle 2": { x: 246, y: 241 },
            "old salty-ps": { x: 68, y: 223 },
            "pharaoh-ps": { x: 68, y: 95 },
            "finn midle": { x: 369, y: 589 },
            "finn-ps": { x: 211, y: 589 },
            "finley midle": { x: 370, y: 457 },
            "finley-ps": { x: 245, y: 457 }
        },
        edges: [
            ["root", "corale midle"],
            ["corale midle", "corale-ps"],
            ["corale midle", "tanggo midle 1"],
            ["corale midle", "finn midle"],
            ["tanggo midle 1", "finn midle"],
            ["finn midle", "finn-ps"],
            ["tanggo midle 1", "finley midle"],
            ["old salty midle", "finley midle"],
            ["finley midle", "finley-ps"],
            ["tanggo midle 1", "tanggo midle 2"],
            ["tanggo midle 2", "tanggo-ps"],
            ["tanggo midle 1", "old salty midle"],
            ["old salty midle", "old salty midle 2"],
            ["old salty midle 2", "old salty-ps"],
            ["old salty-ps", "pharaoh-ps"]
        ]
    },
    "kingdom": {
        nodes: {
            "root": { x: 240, y: 845 },
            "gambit-midle": { x: 245, y: 764 },
            "gambit-ps": { x: 336, y: 764 },
            "center bottom": { x: 239, y: 688 },
            "center-botom right": { x: 282, y: 688 },
            "center-top right": { x: 282, y: 612 },
            "center top": { x: 240, y: 612 },
            "victory midle": { x: 240, y: 219 },
            "victoria-ps": { x: 240, y: 123 },
            "jester midle": { x: 111, y: 219 },
            "jester-ps": { x: 111, y: 202 }
        },
        edges: [
            ["root", "gambit-midle"],
            ["gambit-midle", "gambit-ps"],
            ["gambit-midle", "center bottom"],
            ["center bottom", "center-botom right"],
            ["center-botom right", "center-top right"],
            ["center-top right", "center top"],
            ["center top", "victory midle"],
            ["victory midle", "victoria-ps"],
            ["victory midle", "jester midle"],
            ["jester midle", "jester-ps"]
        ]
    },
    "retreat": {
        nodes: {
            "root": { "x": 315, "y": 406 },
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
