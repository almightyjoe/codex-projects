# Physics Explainer Videos

A project for short visual explanations of physics ideas that are commonly misunderstood.

The style is simple: clean animation, plain-language captions, exaggerated scale when needed, and enough physics accuracy to build intuition without requiring equations first.

## First Video

### 01. Tides and the Earth-Moon Barycenter

Core idea: the Earth and Moon orbit a shared center of gravity, and a liquid-covered Earth is pulled into an elongated shape rather than remaining perfectly spherical.

Current render:

`../tides_barycenter_video/earth_moon_tides_barycenter.mp4`

Current script:

`../tides_barycenter_video/render_tides_barycenter.py`

## 10-Video Roadmap

1. **Tides and the Earth-Moon Barycenter**
   - Why there are two high-tide bulges.
   - Why the barycenter matters.
   - Why a liquid-covered Earth becomes slightly elliptical.

2. **Why Astronauts Float in Orbit**
   - They are not outside gravity.
   - They are continuously falling around Earth.
   - Orbit is sideways falling fast enough to keep missing the ground.

3. **Why Airplanes Fly**
   - Lift from pressure differences and air deflection.
   - Why “equal transit time” is misleading.
   - Angle of attack, wing shape, and airflow.

4. **Why Seasons Happen**
   - Seasons are caused by Earth’s axial tilt, not distance from the Sun.
   - Sun angle and day length control heating.
   - Opposite seasons in opposite hemispheres.

5. **Why the Sky Is Blue and Sunsets Are Red**
   - Scattering depends on wavelength.
   - Blue light scatters more strongly.
   - At sunset, sunlight travels through more atmosphere.

6. **How Gravity Bends Light**
   - Light follows curved spacetime.
   - Gravitational lensing around massive objects.
   - Why this is not ordinary “pulling” like a rope.

7. **Why Time Slows Down Near Massive Objects**
   - Gravity affects time.
   - Clocks closer to a massive body tick slower.
   - GPS needs relativity corrections.

8. **What Temperature Really Means**
   - Temperature is average microscopic motion.
   - Heat is energy transfer, not a substance.
   - Why metal feels colder than wood at the same temperature.

9. **How Electricity Actually Moves Through a Wire**
   - Electrons drift slowly.
   - Energy moves through the electromagnetic field.
   - Why a light turns on almost instantly.

10. **Why Boats Float and Submarines Sink**
    - Buoyancy is displaced fluid pushing back.
    - Density determines floating or sinking.
    - Submarines control buoyancy with ballast.

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
      output.mp4
      preview.png
      notes.md
    02_astronauts_float/
      render.py
      output.mp4
      preview.png
      notes.md
```

## GitHub

This workspace is not currently a Git repository. To publish it, create or choose a GitHub repository, then initialize Git locally and push the project.
