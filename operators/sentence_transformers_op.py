from sentence_transformers import SentenceTransformer
from sentence_transformers import util

from dora import DoraStatus
import os
import sys
import inspect
import torch
import pyarrow as pa
from typing import Callable, Optional, Union

SHOULD_NOT_BE_INCLUDED = [
    "utils.py",
    "sentence_transformers_op.py",
    "chatgpt_op.py",
    "whisper_op.py",
    "microphone_op.py",
    "object_detection_op.py",
    "bot.py",
    "web.py",
    "plot.py"
]


## Get all python files path in given directory
def get_all_functions(path):
    raw = []
    paths = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                if file in SHOULD_NOT_BE_INCLUDED:
                    continue
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf8") as f:
                    ## add file folder to system path
                    sys.path.append(root)
                    ## import module from path
                    raw.append(f.read())
                    paths.append(path)

    return raw, paths


def search(query_embedding, corpus_embeddings, paths, raw, k=5, file_extension=None):
    # TODO: filtering by file extension
    cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    top_results = torch.topk(cos_scores, k=min(k, len(cos_scores)), sorted=True)
    out = []
    for score, idx in zip(top_results[0], top_results[1]):
        out.extend([raw[idx], paths[idx], score])
    return out


class Operator:
    """ """

    def __init__(self):
        ## TODO: Add a initialisation step
        self.model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        self.encoding = []
        # file directory
        path = os.path.dirname(os.path.abspath(__file__))

        self.raw, self.path = get_all_functions(path)
        # Encode all files
        self.encoding = self.model.encode(self.raw)

    def on_event(
        self,
        dora_event: dict,
        send_output: Callable[[str, Union[bytes, pa.Array], Optional[dict]], None],
    ) -> DoraStatus:
        if dora_event["type"] == "INPUT":
            return self.on_input(dora_event, send_output)
        return DoraStatus.CONTINUE
    
    def on_input(
        self,
        dora_input: dict,
        send_output: Callable[[str, Union[bytes, pa.Array], Optional[dict]], None],
    ) -> DoraStatus:
        if dora_input["id"] == "query":
            values = dora_input["value"].to_pylist()

            # Only modify code if the word please is used.
            if not ("please" in values[0] or "Please" in values[0]):
                print("Did not use please word")
                return DoraStatus.CONTINUE

            query_embeddings = self.model.encode(values)
            output = search(
                query_embeddings,
                self.encoding,
                self.path,
                self.raw,
            )
            [raw, path, score] = output[0:3]
            print(
                (
                    score,
                    pa.array([{"raw": raw, "path": path, "query": values[0]}]),
                )
            )
            send_output(
                "raw_file",
                pa.array([{"raw": raw, "path": path, "query": values[0]}]),
                dora_input["metadata"],
            )

        return DoraStatus.CONTINUE


if __name__ == "__main__":
    operator = Operator()
