from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    mothbox_root: Path
    custom_root: Path

    @property
    def controls_root(self) -> Path:
        return self.custom_root / "system" / "controls"

    @property
    def settings_csv(self) -> Path:
        return self.custom_root / "mothbox_settings.csv"

    @property
    def default_settings_csv(self) -> Path:
        return self.controls_root / "defaults" / "default_settings.csv"

    @property
    def timezone_list(self) -> Path:
        return self.custom_root / "timezone_list.txt"

    @classmethod
    def real(cls) -> "Paths":
        return cls(
            mothbox_root=Path("/home/pi/Desktop/Mothbox"),
            custom_root=Path("/boot/firmware/mothbox_custom"),
        )

    @classmethod
    def under(cls, root: Path) -> "Paths":
        root = Path(root)
        return cls(
            mothbox_root=root / "home/pi/Desktop/Mothbox",
            custom_root=root / "boot/firmware/mothbox_custom",
        )
