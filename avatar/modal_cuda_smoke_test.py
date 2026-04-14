"""
CUDA Smoke Test — Prove the training image can compile and run GaussianTalker.
Three checks only:
  1. nvcc --version
  2. CUDA_HOME is set
  3. CUDA submodules compile and import
"""

import modal
import json

app = modal.App("champ-cuda-smoke")

smoke_image = (
    modal.Image.from_registry("nvidia/cuda:11.8.0-devel-ubuntu22.04", add_python="3.10")
    .apt_install("git", "ninja-build", "g++", "build-essential", "clang")
    .pip_install(
        "torch==2.1.0", "torchvision==0.16.0",
        extra_index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install("wheel", "setuptools")
)


@app.function(image=smoke_image, gpu="A10G", timeout=1800)
def cuda_smoke_test():
    """Compile CUDA submodules and verify they import."""
    import subprocess
    import os
    import sys

    results = {}

    # Check 1: nvcc
    proc = subprocess.run("nvcc --version", shell=True, capture_output=True, text=True)
    results["nvcc"] = proc.stdout.strip().split("\n")[-1] if proc.returncode == 0 else f"FAIL: {proc.stderr}"

    # Check 2: CUDA_HOME
    cuda_home = os.environ.get("CUDA_HOME", os.environ.get("CUDA_PATH", ""))
    if not cuda_home:
        # Try to find it
        for path in ["/usr/local/cuda", "/usr/local/cuda-11.8", "/usr/lib/cuda"]:
            if os.path.exists(path):
                cuda_home = path
                os.environ["CUDA_HOME"] = path
                break
    results["CUDA_HOME"] = cuda_home if cuda_home else "NOT FOUND"

    if not cuda_home:
        return json.dumps(results, indent=2)

    # Check 3: Clone and compile
    GT_REPO = "/tmp/GaussianTalker"

    print("[SMOKE] Cloning GaussianTalker...")
    subprocess.run(
        f"git clone https://github.com/cvlab-kaist/GaussianTalker.git {GT_REPO}",
        shell=True, capture_output=True,
    )

    # Clone submodules explicitly
    print("[SMOKE] Cloning rasterizer submodule...")
    subprocess.run(
        f"git clone --recursive https://github.com/joungbinlee/custom-bg-depth-diff-gaussian-rasterization.git {GT_REPO}/submodules/custom-bg-depth-diff-gaussian-rasterization",
        shell=True, capture_output=True,
    )
    print("[SMOKE] Cloning simple-knn submodule...")
    subprocess.run(
        f"git clone https://github.com/camenduru/simple-knn.git {GT_REPO}/submodules/simple-knn",
        shell=True, capture_output=True,
    )

    # Set C++ compiler explicitly
    os.environ["CXX"] = "g++"
    os.environ["CC"] = "gcc"

    # Build rasterizer
    print("[SMOKE] Building custom-bg-depth-diff-gaussian-rasterization...")
    proc = subprocess.run(
        "CXX=g++ CC=gcc python setup.py install",
        shell=True, capture_output=True, text=True,
        cwd=f"{GT_REPO}/submodules/custom-bg-depth-diff-gaussian-rasterization",
    )
    if proc.returncode == 0:
        results["rasterizer_build"] = "PASS"
    else:
        results["rasterizer_build"] = f"FAIL: {proc.stderr[-500:]}"
        return json.dumps(results, indent=2)

    # Build simple-knn
    print("[SMOKE] Building simple-knn...")
    proc = subprocess.run(
        "CXX=g++ CC=gcc python setup.py install",
        shell=True, capture_output=True, text=True,
        cwd=f"{GT_REPO}/submodules/simple-knn",
    )
    if proc.returncode == 0:
        results["simple_knn_build"] = "PASS"
    else:
        results["simple_knn_build"] = f"FAIL: {proc.stderr[-500:]}"
        return json.dumps(results, indent=2)

    # Import test
    print("[SMOKE] Testing imports...")
    try:
        import diff_gaussian_rasterization
        results["import_rasterizer"] = "PASS"
    except Exception as e:
        results["import_rasterizer"] = f"FAIL: {e}"

    try:
        from simple_knn._C import distCUDA2
        results["import_simple_knn"] = "PASS"
    except Exception as e:
        results["import_simple_knn"] = f"FAIL: {e}"

    return json.dumps(results, indent=2)
