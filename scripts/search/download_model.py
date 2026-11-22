#!/usr/bin/env python3
"""
module_name: download_model.py
description: Download and check the optional local embedding and re-ranking models. Runs only when you start it on purpose. Search works without it (hash embedder).
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported. Needs --yes-download because it uses the network once. Nothing else in Tollgate downloads a model.
usage: python3 download_model.py --yes-download [--no-rerank]
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
import embedder as embedder_mod  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download the optional local models.")
    parser.add_argument("--yes-download", action="store_true", help="Required. Confirms you want a network download.")
    parser.add_argument("--no-rerank", action="store_true", help="Skip the re-ranker")
    args = parser.parse_args(argv)
    if not args.yes_download:
        print("Nothing downloaded. Run again with --yes-download to fetch the models over the network.")
        return 2
    embedder_mod._stub_backend()
    from sentence_transformers import CrossEncoder, SentenceTransformer
    print(f"Downloading embedding model: {config.MODEL_NAME}")
    trust = os.environ.get(config.ENV_TRUST_REMOTE_CODE, "").strip() == "1"
    model = SentenceTransformer(config.MODEL_NAME, trust_remote_code=trust)
    test = model.encode(["test"], normalize_embeddings=True)
    print(f"Embedding model ready, output dim: {test.shape[1]}")
    if not args.no_rerank:
        print(f"Downloading reranker: {config.RERANK_MODEL}")
        CrossEncoder(config.RERANK_MODEL)
        print("Reranker ready")
    print("Models downloaded and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
