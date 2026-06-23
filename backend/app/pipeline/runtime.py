from __future__ import annotations

import importlib


REQUIRED_MODULES = {
    "cv2": "opencv-python-headless",
    "numpy": "numpy",
    "torch": "torch",
    "torchvision": "torchvision",
}


def load_runtime_modules() -> dict[str, object]:
    modules: dict[str, object] = {}
    missing: list[str] = []
    for module_name, package_name in REQUIRED_MODULES.items():
        try:
            modules[module_name] = importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)
    if missing:
        packages = " ".join(sorted(set(missing)))
        raise RuntimeError(
            "The computer-vision runtime dependencies are not installed. "
            f"Install them with: pip install {packages}"
        )
    return modules

