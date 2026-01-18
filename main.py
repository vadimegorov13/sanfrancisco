from src.utils.data_loader import download_sf_dataset_to_mysql


def main():
  download_sf_dataset_to_mysql(
    dataset_id='vw6y-z8j6',
    table_name='sf_311_filtered',
    select_columns='service_request_id, requested_datetime, service_name, status_description',
    where_clause="status_description = 'Closed'",
    max_rows=1000,
    if_exists='replace',
    show_sample=True,
  )

if __name__ == '__main__':
  main()
