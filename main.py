import argparse

from src.utils.data_loader import inject_sf_dataset_to_mysql_db


def load_data(args):
  """
  Load SF dataset into MySQL.
  """
  print(f"Injecting {args.dataset} into table '{args.table}'...")
  
  inject_sf_dataset_to_mysql_db(
    dataset_id=args.dataset,
    table_name=args.table,
    select_columns=args.columns or '*',
    where_clause=args.where or None,
    max_rows=args.limit or None,
    if_exists=args.exists or 'replace',
    show_sample=args.sample == 1
  )


def analyze_data(args):
  """
  Run data analysis.
  """

  print("Running analysis...")
  # TODO: Implement analysis functions
  print("Analysis complete!")


def main():
  parser = argparse.ArgumentParser(
    description='SF Data Mining Project',
    formatter_class=argparse.RawDescriptionHelpFormatter
  )
  
  subparsers = parser.add_subparsers(dest='command', help='Available commands')
  
  # Load data command
  load_parser = subparsers.add_parser('load', help='Load SF data into MySQL')
  load_parser.add_argument('--dataset', type=str, help='SF dataset ID (example: vw6y-z8j6)', required=True)
  load_parser.add_argument('--table', type=str, help='Table name (example: sf_311_cases)', required=True)
  load_parser.add_argument('--limit', type=int, help='Max rows to download (default: none)')
  load_parser.add_argument('--columns', type=str, help='Comma-separated column names (default: all)')
  load_parser.add_argument('--where', type=str, help='WHERE clause for filtering (default: none)')
  load_parser.add_argument('--exists', choices=['fail', 'replace', 'append'], type=str, help='What to do if table exists: replace | fail | append (default: replace)')
  load_parser.add_argument('--sample', choices=[0, 1], type=int, help='Show sample after loading (default: 0)')
  load_parser.set_defaults(func=load_data)
  
  # Analyze command
  analyze_parser = subparsers.add_parser('analyze', help='Run data analysis')
  analyze_parser.set_defaults(func=analyze_data)
  
  args = parser.parse_args()
  
  if not args.command:
    parser.print_help()
    return
  
  args.func(args)


if __name__ == '__main__':
  main()
