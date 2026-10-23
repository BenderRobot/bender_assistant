import argparse
import json
from pathlib import Path

from .catalog import Catalog
from .transfer import pack, install


def main():
    parser=argparse.ArgumentParser(description='Dépôt et import de médias Bender, hors Git')
    sub=parser.add_subparsers(dest='command',required=True)
    bundle=sub.add_parser('pack');bundle.add_argument('--source',type=Path,required=True);bundle.add_argument('--archive',type=Path,required=True);bundle.add_argument('--known',type=Path)
    incoming=sub.add_parser('import-archive');incoming.add_argument('archive',type=Path)
    sub.add_parser('inventory')
    sub.add_parser('process-pending')
    args=parser.parse_args()
    if args.command=='pack':
        known=json.loads(args.known.read_text(encoding='utf-8-sig')) if args.known else []
        print(f'{pack(args.source,args.archive,known)} nouveaux médias préparés.')
    else:
        from dotenv import load_dotenv
        from bender_voice.config import load_config
        load_dotenv()
        catalog=Catalog(Path(load_config()['data_dir'])/'media')
        if args.command=='inventory':print(json.dumps(catalog.inventory()))
        elif args.command=='import-archive':print(f'{install(args.archive,catalog)} nouveaux médias importés.')
        else:
            from bender_voice.hardware import Hardware
            from bender_brain.client import Client
            from .worker import Worker
            worker=Worker(catalog,Hardware(load_config()),Client());worker.run();print(worker.message)


if __name__=='__main__':main()
