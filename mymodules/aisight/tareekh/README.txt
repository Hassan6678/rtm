1 - We used date isoformat through out this code, which looks like this,

%Y-%m-%d
2022-03-31


2 - python-dateutils module has a function name "relativedelta" which has arguments "with s" and "without s", e.g., 
relativedelta(months=1) or relativedelta(month=1), 
kindly read documentation to understand the difference. because we have used this extensively in this module.
