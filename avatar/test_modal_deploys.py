"""
Quick test script for Modal GPU deployments.
Run after deploying both services:
    python avatar/test_modal_deploys.py
"""

import sys
import time


def test_personalive():
    """Test PersonaLive A100 deployment."""
    print("\n=== PersonaLive A100 Health Check ===")
    try:
        import modal
        cls = modal.Cls.from_name("champ-personalive", "PersonaLiveEngine")
        engine = cls()

        start = time.time()
        result = engine.health.remote()
        elapsed = time.time() - start

        print(f"  Status:    {result.get('status', 'unknown')}")
        print(f"  Pipeline:  {'loaded' if result.get('pipeline_loaded') else 'NOT loaded'}")
        print(f"  Device:    {result.get('device', 'unknown')}")
        print(f"  Error:     {result.get('load_error', 'none')[:200] if result.get('load_error') else 'none'}")
        print(f"  Latency:   {elapsed:.1f}s (includes cold start)")
        return result
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_gaussian_trainer():
    """Test GaussianAvatars training deployment."""
    print("\n=== GaussianAvatars Trainer Health Check ===")
    try:
        import modal
        cls = modal.Cls.from_name("champ-gaussian-training", "GaussianTrainer")
        trainer = cls()

        start = time.time()
        result = trainer.health.remote()
        elapsed = time.time() - start

        print(f"  Status:    {result.get('status', 'unknown')}")
        print(f"  GPU:       {result.get('gpu', 'unknown')} ({result.get('vram_gb', 0)}GB)")
        print(f"  CUDA ext:  {'compiled' if result.get('cuda_extensions_compiled') else 'MISSING'}")
        print(f"  FLAME:     {'uploaded' if result.get('flame_model_uploaded') else 'NOT uploaded'}")
        print(f"  PyTorch:   {result.get('pytorch_version', 'unknown')}")
        print(f"  CUDA:      {result.get('cuda_version', 'unknown')}")
        print(f"  Latency:   {elapsed:.1f}s (includes cold start)")

        # List avatars
        avatars = trainer.list_avatars.remote()
        print(f"  Avatars:   {avatars.get('avatars', {})}")
        return result
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_personalive_load():
    """Test PersonaLive actually loading models (the real test)."""
    print("\n=== PersonaLive Model Load Test ===")
    try:
        import modal
        cls = modal.Cls.from_name("champ-personalive", "PersonaLiveEngine")
        engine = cls()

        # Read Genesis reference image
        ref_path = "models/avatars/genesis/reference.png"
        with open(ref_path, "rb") as f:
            image_bytes = f.read()
        print(f"  Reference image: {len(image_bytes)} bytes")

        # Try generating a static avatar (triggers full pipeline load)
        print("  Calling generate_static_avatar (this loads all 6 models)...")
        start = time.time()
        result = engine.generate_static_avatar.remote(image_bytes, num_frames=4)
        elapsed = time.time() - start

        if "error" in result:
            print(f"  ERROR: {result['error'][:500]}")
        else:
            num_frames = result.get("num_frames", 0)
            print(f"  Generated {num_frames} frames in {elapsed:.1f}s")
            print(f"  FPS: {result.get('fps', 0)}")

            # Save first frame
            if result.get("frames"):
                with open("models/avatars/genesis/personalive_test_frame.png", "wb") as f:
                    f.write(result["frames"][0])
                print("  Saved test frame to models/avatars/genesis/personalive_test_frame.png")

        return result
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "health" in args:
        test_personalive()
        test_gaussian_trainer()

    if "load" in args or "personalive" in args:
        test_personalive_load()

    if "all" in args:
        test_personalive()
        test_gaussian_trainer()
        test_personalive_load()

    print("\nDone.")
