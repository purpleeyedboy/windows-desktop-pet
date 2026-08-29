### Task 3: Generate Only the Hidden Fill Sources

**Files:**
- Create: `assets/rig/v1/source/ai/body-fill-raw.png`
- Create: `assets/rig/v1/source/ai/eye-fill-raw.png`
- Modify: `assets/rig/v1/source/authoring.json`

**Interfaces:**
- Consumes: the two generated guides and canonical image.
- Produces: two local raster sources plus exact prompts and output SHA-256 values in `authoring.json`. No generated pixel is accepted outside the fixed masks in Task 4.

- [ ] **Step 1: Load the required image-editing skill and inspect both guides**

Read `$imagegen` completely, then inspect `body-fill-guide.png` and `eye-fill-guide.png` at original resolution. If the green body region touches an external antialiased silhouette or either eye ellipse includes nose/eyelid fur, stop and correct Task 2 coordinates before generation.

- [ ] **Step 2: Generate the hidden shoulder/neck fill**

Invoke image editing with `body-fill-guide.png` and `canonical-idle.png` as references and this exact prompt:

```text
Edit the supplied 2:3 cat image guide. Replace only the solid neon-green internal region with the anatomically plausible shoulder, upper chest, and torso fur that would exist behind the removed head and neck of this exact orange-and-white Devon Rex cat. Continue the same short curly fur texture, orange tabby markings, white chest, lighting direction, focus, and photographic detail. Do not add a head, face, eye, ear, collar, bell, leg, text, outline, colored fringe, or background. Preserve the canvas composition and transparent surroundings. The result is a hidden fill source; all non-green content should remain visually aligned with the reference.
```

Save the returned PNG as `assets/rig/v1/source/ai/body-fill-raw.png`. If the service returns the same 2:3 aspect ratio at a larger resolution, retain it unchanged; Task 4 performs the only normalization.

- [ ] **Step 3: Generate the hidden eye-socket fill**

Invoke image editing with `eye-fill-guide.png` and `canonical-idle.png` as references and this exact prompt:

```text
Edit the supplied 2:3 cat image guide. Replace only the two solid neon-green iris regions with the natural eye-socket content behind movable irises for this exact cat: pale green-gray eye interior, subtle eyelid shadow, and the original short fur and lighting at each eye. Keep both eye shapes, eye corners, eyelids, face, nose, markings, proportions, camera, and transparent background aligned exactly. Do not add pupils, irises, extra highlights, extra eyes, text, outline, or colored fringe. This is a hidden underlay, not a new expression.
```

Save the returned PNG as `assets/rig/v1/source/ai/eye-fill-raw.png`.

- [ ] **Step 4: Record local provenance and commit only these isolated sources**

Add to `authoring.json`:

```json
{
  "ai_fill": {
    "tool": "OpenAI image generation image edit",
    "body_guide": "guides/body-fill-guide.png",
    "body_output": "ai/body-fill-raw.png",
    "eye_guide": "guides/eye-fill-guide.png",
    "eye_output": "ai/eye-fill-raw.png",
    "outside_mask_policy": "discard all generated pixels outside fixed masks"
  }
}
```

Compute and add `body_output_sha256` and `eye_output_sha256` using `Get-FileHash`. Then commit:

```powershell
git add assets/rig/v1/source/ai assets/rig/v1/source/authoring.json
git commit -m "assets: add masked rig fill sources"
```

