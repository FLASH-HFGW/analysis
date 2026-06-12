#!/usr/bin/env python3

import argparse
import gzip
import os
import struct
import sys
import tempfile


HEADER_SIZE = 16
MAX_EVENT_SIZE = 1024 * 1024 * 1024  # 1 GB


MIDAS_BOR = 0x8000
MIDAS_EOR = 0x8001
MIDAS_MESSAGE = 0x8002


def is_midas_internal_event(event_id):
    return event_id >= 0x8000


def open_input(filename):
    if filename.endswith(".gz"):
        return gzip.open(filename, "rb")
    return open(filename, "rb")


def parse_header(header):
    if len(header) != HEADER_SIZE:
        raise ValueError("Header MIDAS troncato")

    vals_le = struct.unpack("<HHIII", header)
    data_size_le = vals_le[4]

    if data_size_le <= MAX_EVENT_SIZE:
        return vals_le

    vals_be = struct.unpack(">HHIII", header)
    data_size_be = vals_be[4]

    if data_size_be <= MAX_EVENT_SIZE:
        return vals_be

    raise ValueError(
        f"Header non plausibile: data_size LE={data_size_le}, BE={data_size_be}"
    )


def read_exact(fin, nbytes):
    data = fin.read(nbytes)
    if len(data) != nbytes:
        raise EOFError(f"File troncato: richiesti {nbytes} byte, letti {len(data)}")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Copia i primi N eventi da un file MIDAS .mid.gz a un altro .mid.gz"
    )

    parser.add_argument("-i", "--input", required=True, help="File MIDAS input")
    parser.add_argument("-o", "--output", required=True, help="File MIDAS output")
    parser.add_argument("-n", "--nevents", required=True, type=int, help="Numero eventi da copiare")

    parser.add_argument(
        "--count-normal-only",
        action="store_true",
        help="Conta solo eventi non-interni MIDAS per arrivare a N, ma copia comunque BOR/internal event"
    )

    parser.add_argument(
        "--compresslevel",
        type=int,
        default=1,
        help="Livello compressione gzip, default 1 per scrittura veloce"
    )

    args = parser.parse_args()

    if args.nevents <= 0:
        print("Errore: --nevents deve essere > 0", file=sys.stderr)
        return 1

    outdir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(outdir, exist_ok=True)

    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=os.path.basename(args.output) + ".tmp.",
        suffix=".gz",
        dir=outdir
    )

    copied_records = 0
    counted_events = 0

    try:
        with open_input(args.input) as fin:
            with os.fdopen(tmp_fd, "wb") as raw_out:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_out,
                    compresslevel=args.compresslevel,
                    mtime=0
                ) as fout:

                    while counted_events < args.nevents:
                        header = fin.read(HEADER_SIZE)

                        if len(header) == 0:
                            print("EOF raggiunto prima di copiare tutti gli eventi")
                            break

                        if len(header) != HEADER_SIZE:
                            raise EOFError(
                                f"Header troncato dopo {copied_records} record copiati"
                            )

                        event_id, trigger_mask, serial_number, timestamp, data_size = parse_header(header)

                        payload = read_exact(fin, data_size)

                        fout.write(header)
                        fout.write(payload)

                        copied_records += 1

                        is_internal = is_midas_internal_event(event_id)

                        if args.count_normal_only:
                            if not is_internal:
                                counted_events += 1
                        else:
                            counted_events += 1

                        print(
                            f"record={copied_records} "
                            f"counted={counted_events} "
                            f"event_id={event_id} "
                            f"trigger_mask={trigger_mask} "
                            f"serial={serial_number} "
                            f"timestamp={timestamp} "
                            f"size={data_size} "
                            f"internal={is_internal}",
                            flush=True
                        )

                # Qui il gzip è stato chiuso correttamente.
                # Ora forziamo il flush del file fisico.
                raw_out.flush()
                os.fsync(raw_out.fileno())

        # Rinomina atomica solo se tutto è andato bene.
        os.replace(tmp_name, args.output)

    except Exception:
        print("\nERRORE: output temporaneo lasciato qui:", tmp_name, file=sys.stderr)
        raise

    print(f"DONE: copiati {copied_records} record MIDAS in {args.output}")
    print(f"Eventi contati: {counted_events}")

    return 0


if __name__ == "__main__":
    sys.exit(main())