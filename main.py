from src.database.db_connector import DatabaseConnector


def main():
	with DatabaseConnector() as db:
		query = 'SELECT 1'
		df = db.query(query)

		print(f'Fetched {len(df)} rows')
		print(f'Columns: {df.columns.tolist()}')

		# Clean data
		# df = remove_duplicates(df)
		# df = handle_missing_values(df)

		print(f'After cleaning: {len(df)} rows')

		# TODO
		# - Clustering
		# - Association rules
		# - Anomaly detection


if __name__ == '__main__':
	main()
