#This is a simple function to execute SQL queries from a DuckDB connection or cursor. This is unneccesary now, but it will be useful to have this modularity in the future.
def execute_SQL_query(con, query, dataframe=None):
    #most of my queries use a dataframe as input
    dataframe = dataframe
    return con.execute(query)
