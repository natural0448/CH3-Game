# Local village art

Downloaded and inspected 2026-09-15. All five PNG files are unchanged copies of original 16×16 tiles.

| Local file | Source pack / original name | Source size | Display size |
| --- | --- | --- | --- |
| grass.png | Tiny Town / Tiles/tile_0000.png | 16×16 | 32×32 |
| path.png | Tiny Town / Tiles/tile_0025.png | 16×16 | 32×32 |
| tree.png | Tiny Town / Tiles/tile_0028.png | 16×16 | 32×32 |
| house.png | Tiny Town / Tiles/tile_0086.png (building door/wall; roof drawn separately) | 16×16 | 32×32 |
| hero.png | Tiny Dungeon / Tiles/tile_0084.png | 16×16 | 32×32 |

- [Kenney Tiny Town](https://kenney.nl/assets/tiny-town): CC0. Original ZIP and `sources/town-License.txt` retained.
- [Kenney Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon): CC0. Original ZIP and `sources/dungeon-License.txt` retained.
- Font: [Noto Sans CJK Korean](https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/Korean), `fonts/NotoSansCJKkr-Regular.otf`, SIL Open Font License 1.1; original license in `fonts/LICENSE`.

Paths are relative to config.json, independent of the terminal directory. Main thread loads once and uses nearest-neighbor scaling. Missing art falls back to colored shapes and a path notice. Decorations do not change movement rules. GATHER_TILE=(2,2) remains accessible.
