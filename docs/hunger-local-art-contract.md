# V2.1 hunger graphic art contract

The candidate uses the recovered generated four expression frames, with the
approved canonical neutral as the start/end restoration. Frames must be RGBA,
share the neutral canvas and anchor, and contain clean transparent pixels.
Original approved head, body, eyes, alpha and head-turn settings remain immutable.

`hunger_graphic_assets.load_hunger_graphic_assets(neutral)` validates and loads
this recovered frame source. It returns finite `AnimationSequence` clips for
Hungry/Severe and a critical expression frame. `HungerGraphicRuntime` selects
clips; it does not draw replacement mouth shapes, resize individual body parts,
or own a second application state.

All visible action frames enter the shared `PetWindow` graphic player, with
explicit frame durations, canonical restoration and real coordinator tokens.
Critical is an orthogonal idle expression. During menu/drag/feed activity it is
hidden without blocking feeding or shutdown. The images remain candidate art
until actual-size and Windows visual acceptance.
