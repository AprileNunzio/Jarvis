import asyncio
import json
import sys


async def main(path: str) -> dict:
    from shazamio import Shazam
    shazam = Shazam(language="it-IT", endpoint_country="IT")
    with open(path, "rb") as fh:
        data = fh.read()
    recognize = getattr(shazam, "recognize", None) or shazam.recognize_song
    return await recognize(data)


if __name__ == "__main__":
    try:
        result = asyncio.run(asyncio.wait_for(main(sys.argv[1]), 25))
    except TypeError:
        from shazamio import Shazam

        async def fallback():
            s = Shazam()
            return await (getattr(s, "recognize", None) or s.recognize_song)(open(sys.argv[1], "rb").read())
        result = asyncio.run(fallback())
    print(json.dumps(result or {}, ensure_ascii=False))
