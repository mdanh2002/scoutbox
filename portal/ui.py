COUNTRIES = [
'Afghanistan','Albania','Algeria','Andorra','Angola','Antigua and Barbuda','Argentina','Armenia','Australia','Austria','Azerbaijan',
'Bahamas','Bahrain','Bangladesh','Barbados','Belarus','Belgium','Belize','Benin','Bhutan','Bolivia','Bosnia and Herzegovina','Botswana','Brazil','Brunei','Bulgaria','Burkina Faso','Burundi',
'Cambodia','Cameroon','Canada','Cape Verde','Central African Republic','Chad','Chile','China','Colombia','Comoros','Costa Rica','Croatia','Cuba','Cyprus','Czechia',
'Democratic Republic of the Congo','Denmark','Djibouti','Dominica','Dominican Republic','Ecuador','Egypt','El Salvador','Equatorial Guinea','Eritrea','Estonia','Eswatini','Ethiopia',
'Fiji','Finland','France','Gabon','Gambia','Georgia','Germany','Ghana','Greece','Grenada','Guatemala','Guinea','Guinea-Bissau','Guyana','Haiti','Honduras','Hungary',
'Iceland','India','Indonesia','Iran','Iraq','Ireland','Israel','Italy','Ivory Coast','Jamaica','Japan','Jordan','Kazakhstan','Kenya','Kiribati','Kuwait','Kyrgyzstan',
'Laos','Latvia','Lebanon','Lesotho','Liberia','Libya','Liechtenstein','Lithuania','Luxembourg','Madagascar','Malawi','Malaysia','Maldives','Mali','Malta','Marshall Islands','Mauritania','Mauritius','Mexico','Micronesia','Moldova','Monaco','Mongolia','Montenegro','Morocco','Mozambique','Myanmar',
'Namibia','Nauru','Nepal','Netherlands','New Zealand','Nicaragua','Niger','Nigeria','North Korea','North Macedonia','Norway','Oman','Pakistan','Palau','Palestine','Panama','Papua New Guinea','Paraguay','Peru','Philippines','Poland','Portugal','Qatar','Republic of the Congo','Romania','Russia','Rwanda',
'Saint Kitts and Nevis','Saint Lucia','Saint Vincent and the Grenadines','Samoa','San Marino','Sao Tome and Principe','Saudi Arabia','Senegal','Serbia','Seychelles','Sierra Leone','Singapore','Slovakia','Slovenia','Solomon Islands','Somalia','South Africa','South Korea','South Sudan','Spain','Sri Lanka','Sudan','Suriname','Sweden','Switzerland','Syria',
'Taiwan','Tajikistan','Tanzania','Thailand','Timor-Leste','Togo','Tonga','Trinidad and Tobago','Tunisia','Turkey','Turkmenistan','Tuvalu','Uganda','Ukraine','United Arab Emirates','United Kingdom','United States','Uruguay','Uzbekistan','Vanuatu','Vatican City','Venezuela','Vietnam','Yemen','Zambia','Zimbabwe',
'Remote worldwide',
# Recruiter-region labels used by job boards and remote listings. They are accepted
# wherever ScoutBox offers a Country/Region picker.
'Europe','EU','EEA','EU/EEA','UK & Europe','UK & Ireland','DACH','CEE','Benelux','Nordics','APAC','ASEAN','ANZ','Asia','EMEA','MENA','GCC','Middle East','Africa','LATAM','South America','Central America','Caribbean','North America','Americas','Worldwide','Global'
]

CURRENCIES=['SGD','USD','EUR','GBP','AUD','CAD','JPY','CNY','HKD','NZD','CHF','INR','MYR','THB','PHP','IDR','KRW','AED']

NAV_GROUPS = [
    ('Quick View', [('dashboard','Dashboard'),('profile','Candidate Profile'),('scope','Engagement Preferences'),('about','About ScoutBox')]),
    ('Discovery', [('campaigns','Campaigns'),('opportunities','Opportunities'),('cold_contact','Hidden Leads'),('facebook_pages','Facebook Pages'),('blacklist','Blacklist')]),
    ('Applications', [('applications','Applications & Outreach'),('links','Tracking Links'),('contacts','Address Book')]),
    ('Analytics', [('stats','Statistics'),('telemetry','Resource Usage')]),
    ('Diagnostics', [('search_log','Search Activity'),('gpt_log','AI Requests'),('audit','Audit Trail'),('email_history','Email History')]),
    ('System', [('settings','Configuration'),('recycle_bin','Recycle Bin'),('logout','Logout')]),
]


NAV_PARENT={route:(group,label) for group,items in NAV_GROUPS for route,label in items}
