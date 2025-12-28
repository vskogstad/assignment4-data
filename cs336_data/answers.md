look_at_cc

a) I get http://0371rykj.com/ipfhsb/34.html which firefox believes is a phishing website so it blocks it. It seems to be some kind of product webpage for what I guess is a chinese electronic instrument manufacturer. I see referances to wattage and the name Shanghai Linpin Instrument Stock Co Ltd.

b) Hard to say what is worthless as I don't understand chinese. I guess any single character line has limited value and would maybe learn the model to predict random newlines after one of these words? The short sentences are likely still coherent and will learn the model to predict reasonable words. A higher level model might learn something about the order in which product information is typically listet. A coding model have use from seeing the information laid out to create a website, but then keeping the raw HTML as training data is likely better.

c) A chinese/multilingual model serving enterprise customers/making a coding model or serving this particular field could have use for the data. A model that shouldn't know chinese will be useless.

d) Starting from the next file:
1: CN, Discuss message board main page showing links to discussions.
2: EN, US National Congress on Computational Mechanics. Some info about the org, not a lot on the page.
3: CN, product webpage.
4: CN, product webpage.
5: CN, header seems identical to 3. Listing of a girls? height, age, weight? Lots of spammy looking lines.
6: CN, 18sex in the domain name, listings of something..
7: NL, Private blog main page, not much text. 
8-10: GR, Travel agency? Very little text.
11: CN, Product website. First one where I see . and , so maybe more usefull text? Not high quality.
12: TR, Product manual, just chapter titles.
13: EN, Casino blog, seems very low effort/quality.
14: EN, 404
15- 16: CN, Both have a few paragraphs of text. The first one also lists many other blog links?
17: CN, discussion about mostly western pop-music? Might be somewhat useable.
18: CN, short, no longer text.
19: CN, products again, I think the listings of age/height/weight must be just default settings for the product. Some 1-liner reviews?
20: EN, Failed serch term at library site.
21: CN, same as 19 basically.
22: CN, Same as 19. I've flipflopped back. They are listing the age and blood type too though, always girls in 19-2x age range. Best case chinese celebrities? 
23: CN, Same. Another 19 year old <50 kg.
24: SP, Blog, political/newsworthy. Don't think it's super trustworthy.
25: DK. Marketing for window cleaning, low quality paid blog/advertisement.

Overall browsed 150 first hits. Not any sample that I would consider high quality among them. The spanish blog in number 24 and main page in number 2 is probably the highest quality. Lots of LLM-generated content. Don't believe this is a crawl from 2018.



extract_text
b)
Overall There is little difference between the two texts, my version makes bulletpoints where wet uses just plain newline. Mine also keeps references to images within the text.


Wet:
Welcome to USNCCM13! | USNCCM 13
Skip to main content
USNCCM 13
13th US National Congress on Computational Mechanics
San Diego, CA
July 26-30, 2015
Main menu
Home
Congress Information
Important Dates
Organization
Local Organizing Committee
Scientific Organizing Committee
USACM Advisory Committee
Contact
Congress Co-Chairs
Administrative Contact
Plenary and Semi-Plenary Speakers
Minisymposia
Congress Minisymposia
Minisymposia Organizers' Page
Abstract Submission
Program
Technical Program
Social Program
Presenter Instructions
AHPCRC Student Poster Competition
Short Courses
Financial Assistance
USNCCM13 Travel Awards Information and Application
Accommodations
Registration
Sponsors and Exhibitors
Venue
Travel Information
Welcome to USNCCM13!
New! Photos from the congress are now available here.
The printed program is now available for downloading here.
Abstracts for USNCCM13 are now available, ordered by presenting author: A-M and N-Z
A preliminary searchable schedule is now available. Go to http://13.usnccm.org/program for more information.
The dates of the technical program of the Congress are Monday, July 27, 2015 - Thursday, July 30, 2015.
Pre-congress short courses will take place on July 26, 2015.
Welcome to USACM's 13th U.S. National Congress on Computational Mechanics (USNCCM13) to be held in San Diego, California, at the Manchester Grand Hyatt, July 26-30, 2015.
From their inception in 1991, the biennial congresses of the U.S. Association for Computational Mechanics have become major scientific events, drawing computational engineers and scientists worldwide from government, academia, and industry. The congress provides a forum for researchers and practitioners all over the world to discuss the latest advancements and future directions in fields pertaining to computational engineering and sciences.
The congress will feature plenary speakers, over 100 mini-symposia with keynote lectures and contributed talks, a student poster competition, and exhibits from various sponsors.
Area Information
Things to do in San Diego
Things to do in Southern California
University of California, San Diego
© Copyright 2013, USACM
Hosting provided by: Siriad
© Copyright 2012, USACM
Hosting provided by: Siriad


Mine:

"Skip to main content\nHome\nUSNCCM 13\n13th US National Congress on Computational Mechanics\nSan Diego, CA\nJuly 26-30, 2015\n\nMain menu\n\n  • Home\n\nCongress Information\n\n  • Important Dates\n  • Organization\n    • Local Organizing Committee\n    • Scientific Organizing Committee\n    • USACM Advisory Committee\n  • Contact\n    • Congress Co-Chairs\n    • Administrative Contact\n  • Plenary and Semi-Plenary Speakers\n  • Minisymposia\n    • Congress Minisymposia\n    • Minisymposia Organizers' Page\n  • Abstract Submission\n  • Program\n    • Technical Program\n    • Social Program\n  • Presenter Instructions\n  • AHPCRC Student Poster Competition\n  • Short Courses\n  • Financial Assistance\n    • USNCCM13 Travel Awards Information and Application\n  • Accommodations\n  • Registration\n  • Sponsors and Exhibitors\n  • Venue\n  • Travel Information\n\nWelcome to USNCCM13!\n\nNew!\xa0 Photos from the congress are now available here.\n\nThe printed program is now available for downloading here.\n\nAbstracts for USNCCM13 are now available, ordered by presenting author: A-M and N-Z\n\n\xa0\n\nA preliminary searchable schedule is now available.\xa0 Go to http://13.usnccm.org/program for more information.\n\nThe dates of the technical program of the Congress are Monday, July 27, 2015 - Thursday, July 30, 2015.\n\nPre-congress short courses will take place on July 26, 2015.\n\nWelcome to USACM's 13th U.S. National Congress on Computational Mechanics (USNCCM13) to be held in San Diego, California, at the Manchester Grand Hyatt, July 26-30, 2015.\n\nFrom their inception in 1991, the biennial congresses of the U.S. Association for Computational Mechanics have become major scientific events, drawing computational engineers and scientists worldwide from government, academia, and industry.\xa0 The congress provides a forum for researchers and practitioners all over the world to discuss the latest advancements and future directions in fields pertaining to computational engineering and sciences.\n\nThe congress will feature plenary speakers, over 100 mini-symposia with keynote lectures and contributed talks, a student poster competition, and exhibits from various sponsors.\n\n\xa0\n\nbridge_USACM_trim.jpg\n\nArea Information\n\n  • Things to do in San Diego\n  • Things to do in Southern California\n  • University of California, San Diego\n\n\xa0\n\nUSACM_LOGO_0.jpg\n\n\xa0\xa0\xa0 AHPCRC Logo 2015.jpg\n\n\xa0\n\nElsevierlogo.jpg\n\n\xa0\n\nlogo_simpleware.jpg\n\n\xa0\n\n\xa0\n\n\xa0\n\nSIAM logo.jpg\n\n\xa0\n\n\xa0\n\n\xa0\n\n\xa0\n\n\xa0\n\n© Copyright 2013, USACM\nHosting provided by: Siriad\n\n© Copyright 2012, USACM\nHosting provided by: Siriad\n\nipv6 ready" 