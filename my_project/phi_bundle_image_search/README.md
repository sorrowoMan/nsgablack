# phi_bundle_image_search

Standard nsgablack project scaffold for searching image objectification formula
bundles.

Outer search unit:

`PhiBundle = {phi_lane_1, phi_lane_2, ...}`

Each lane now has typed internal genome fields decoded by family:

- `edge`: direction, local/global scope, edge operator
- `patch_pool`: patch size, stride, pooling operator, spatial region
- `patch_texture`: patch size, stride, texture operator, spatial region
- `orthogonal_frequency`: DCT frequency band and orientation
- `moment`: row/col axis and center/variance statistic
- `region`: center / outer ring / all
- `symmetry`: left-right / top-bottom / all
- `row_projection` and `col_projection`: spatial band selection

The outer genome is not `one continuous param per lane` anymore. It is:

`family toggles -> typed lane fields -> representation/source budget fields`

Layer order:

`nsgablack outer solver -> PhiBundle -> mlblack evaluation proxy -> representation objects -> orthogonal source governance -> logistic head metrics`

This is not point symbolic regression. The outer individual is a formula
collection that generates a feature/object matrix.

Run:

```powershell
python my_project\phi_bundle_image_search\run_solver.py --check
python my_project\phi_bundle_image_search\run_solver.py --suite-id digits_phi_outer_v1
```
