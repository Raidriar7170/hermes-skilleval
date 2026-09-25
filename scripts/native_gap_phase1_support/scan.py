import io
import json
import time
import requests
import pyarrow.parquet as pq
from pathlib import Path

P = Path(
    __import__("os").environ.get(
        "NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"
    )
)


class Remote(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        self.pos = 0
        self.bytes = 0
        self.requests = 0
        self.s = requests.Session()
        r = self.s.get(url, headers={"Range": "bytes=0-7"}, timeout=60)
        r.raise_for_status()
        if r.status_code != 206:
            raise ValueError("Range unsupported")
        self.size = int(r.headers["Content-Range"].split("/")[-1])
        self.bytes += len(r.content)
        self.requests += 1

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, n, w=0):
        self.pos = n if w == 0 else self.pos + n if w == 1 else self.size + n
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        if not n:
            return b""
        r = self.s.get(
            self.url,
            headers={"Range": f"bytes={self.pos}-{min(self.size, self.pos + n) - 1}"},
            timeout=120,
        )
        r.raise_for_status()
        if r.status_code != 206:
            raise ValueError("Range response lost")
        b = r.content
        self.pos += len(b)
        self.bytes += len(b)
        self.requests += 1
        return b


if __name__ == "__main__":
    for name, file in [
        ("SWE-rebench-openhands-trajectories", "trajectories.parquet"),
        ("SWE-rebench", "data/test-00000-of-00002.parquet"),
        ("SWE-rebench", "data/test-00001-of-00002.parquet"),
    ]:
        rev = json.loads((P / (name + "-info.json")).read_text())["sha"]
        t = time.monotonic()
        f = Remote(
            f"https://huggingface.co/datasets/nebius/{name}/resolve/{rev}/{file}"
        )
        q = pq.ParquetFile(f)
        print(
            name,
            file,
            q.metadata.num_rows,
            q.num_row_groups,
            q.schema_arrow.names,
            flush=True,
        )
        cols = (
            ["instance_id", "repo", "trajectory_id"]
            if name.endswith("trajectories")
            else [
                "instance_id",
                "repo",
                "base_commit",
                "docker_image",
                "image_name",
                "license_name",
            ]
        )
        table = q.read(columns=cols)
        rows = table.to_pylist()
        tag = file.replace("/", "_")
        (P / (tag + ".metadata.json")).write_text(json.dumps(rows))
        record = {
            "source": name,
            "revision": rev,
            "file": file,
            "rows": len(rows),
            "size": f.size,
            "transferred_bytes": f.bytes,
            "requests": f.requests,
            "elapsed": time.monotonic() - t,
            "columns": cols,
            "row_groups": q.num_row_groups,
        }
        (P / (tag + ".cost.json")).write_text(json.dumps(record, indent=2))
        print(record, flush=True)
