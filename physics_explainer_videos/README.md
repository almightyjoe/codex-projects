# Physics Explainer Videos

A project for short visual explanations of physics ideas that are commonly misunderstood.

The style is simple: clean animation, plain-language captions, exaggerated scale when needed, and enough physics accuracy to build intuition without requiring equations first.

## Videos

### 01. Tides and the Earth-Moon Barycenter

Core idea: the Earth and Moon orbit a shared center of gravity, and a liquid-covered Earth is pulled into an elongated shape rather than remaining perfectly spherical.

`videos/01_tides_barycenter/earth_moon_tides_barycenter.mp4`

## 10-Video Set

1. **Tides and the Earth-Moon Barycenter**
   - Why there are two high-tide bulges.
   - Why the barycenter matters.
   - Why a liquid-covered Earth becomes slightly elliptical.

2. **Why Seasons Happen**
   - Seasons are caused by Earth’s axial tilt, not distance from the Sun.
   - Sun angle and day length control heating.
   - Opposite seasons in opposite hemispheres.

3. **Why the Sky Is Blue and Sunsets Are Red**
   - Scattering depends on wavelength.
   - Blue light scatters more strongly.
   - At sunset, sunlight travels through more atmosphere.

4. **How Gravity Bends Light**
   - Light follows curved spacetime.
   - Gravitational lensing around massive objects.
   - Why this is not ordinary “pulling” like a rope.

5. **Why Time Slows Down Near Massive Objects**
   - Gravity affects time.
   - Clocks closer to a massive body tick slower.
   - GPS needs relativity corrections.

6. **What Temperature Really Means**
   - Temperature is average microscopic motion.
   - Heat is energy transfer, not a substance.
   - Why metal feels colder than wood at the same temperature.

7. **How Electricity Actually Moves Through a Wire**
   - Electrons drift slowly.
   - Energy moves through the electromagnetic field.
   - Why a light turns on almost instantly.

8. **Why Boats Float and Submarines Sink**
    - Buoyancy is displaced fluid pushing back.
    - Density determines floating or sinking.
    - Submarines control buoyancy with ballast.

9. **Why Airplanes Fly**
   - Lift from pressure differences and air deflection.
   - Why “equal transit time” is misleading.
   - Angle of attack, wing shape, and airflow.

10. **Why Satellites Do Not Fall Straight Down**
    - Near a planet, orbit is continuous falling with sideways speed.
    - The satellite keeps missing the ground.
    - Far from major gravity sources, gravitational pull can be so tiny that motion looks like nearly free-floating drift.

## Suggested Format

- Length: 30 to 90 seconds each.
- Resolution: 1280x720 or 1920x1080.
- Visual style: dark background, clean labels, no clutter.
- Explanation style: one idea per scene, no dense equations unless optional.
- Output: MP4 plus a preview PNG for each video.

## Project Structure

Recommended structure as the project grows:

```text
physics_explainer_videos/
  README.md
  videos/
    01_tides_barycenter/
      render.py
      earth_moon_tides_barycenter.mp4
      preview.png
      notes.md
    02_seasons/
      render.py
      why_seasons_happen.mp4
      preview.png
      notes.md
```

## GitHub

This project lives inside `almightyjoe/codex-projects` under `physics_explainer_videos/`.
