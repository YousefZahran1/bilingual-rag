# Guidelines for Mapping Provider Service Lists to Standard Code Sets (March 2023)

> CHI guideline (March 2023) for mapping provider service lists to standard code sets (SBS).

> Source: data/real2/pdfs/sbs_code_mapping_guidelines.pdf (public document).


## Page 1

GUIDELINES FOR MAPPING
PROVIDER SERVICE LISTS
TO
STANDARD CODE SETS

March 2023


## Page 2

Copyright and Disclaimer
© Council of Health Insurance, Saudi Arabia. All rights reserved. Use of Council of Health Insurance material requires you
to attribute the work (but not in any way that suggests that the Council of Health Insurance endorses you or your use of
the work). The following attribution is preferred:
Source: Council of Health Insurance.
The Council of Health Insurance is a governmental sector entity registered in the Kingdom of Saudi Arabia, CHI Tower,
King Fahd Rd, Al Malqa, Riyadh 11564
While every reasonable care has been taken to ensure the accuracy of the information within this publication, CHI makes
no warranty or guarantee that the information herein is error free and thus will bear no responsibility for the results of
the uses of this document.
Address all inquiries to the Council of Health Insurance (CHI)
(cchi-bs@chi.gov.sa)


## Page 3

CONTENTS
Glossary: ........................................................................................................................................................ 4
What is mapping? ......................................................................................................................................... 4
Why is mapping required? ............................................................................................................................ 4
Recommended Steps for Mapping Process: ................................................................................................. 6
Step I: Formation of the mapping team ................................................................................................... 6
Step II: Clean up and preparation ............................................................................................................. 6
Step III: Mapping ...................................................................................................................................... 8
Key Steps for mapping ........................................................................................................................... 8
Mapping tools and resources: ............................................................................................................... 9
Guidelines for common challenges: .................................................................................................... 10
Step IV: Validation .................................................................................................................................. 18
Step V: Maintenance .............................................................................................................................. 18
Unlisted Codes ............................................................................................................................................ 19
SBS Maintenance: ....................................................................................................................................... 21
Provider-Payer mapping validation process: .............................................................................................. 22
Payer Validation KPI: ................................................................................................................................... 22


## Page 4

GLOSSARY:

ACHI-Australian Classification for Health Interventions
ADA – Australian Dental Association
CHI-Council of Health Insurance
CPOE-Computerized Physician Order Entry
GTIN- Global Trade Item Number-SFDA-GTIN-Medication Codes
GMDN-Global Medical Device Nomenclature
RCM-Revenue Cycle Management
HIM-Health Information Management
SBS-Saudi Billing System
SFDA-Saudi Food and Drug Authority
SNOMED CT – Systematized Nomenclature of Medicine – Clinical Terms
VBHC-Value Based Health Care

WHAT IS MAPPING?
Mapping is defined in its most basic sense as the linking of terminology content between two
terminologies or classification schemes and, in that process, determining how they match, how
they are similar or how they do not match. 1

When maps are created between standard terminologies and classifications, the maps have a
specific purpose. For example, a map between SBS and ACHI. The beginning point of mapping
is the development of heuristics, or "rules of thumb", that allow decisions to be made quickly
without having all of the information at hand, as well as guidelines that support the use case or
purpose of the mapping, respecting the conventions of the source and target to preserve the
granularity and flexibility of both. 2

The purpose of this document is to aid KSA providers with the creation of custom maps from a
non-standard classification, or in-house developed codes and pricelists, to the clinical standards
mandated for claim submission via nphies.
Disclaimer – it is not the intention of this document to provide advice or guidance for pricing.
WHY IS MAPPING REQUIRED?
With the mandate of standard classifications and code sets for all insurance transactions in
nphies, healthcare providers in Saudi Arabia are required to map their internal non-standard

1 Brouch, Kathy. "AHIMA Project Offers Insights into SNOMED, ICD-9-CM Mapping Process." Journal of AHIMA 74, no.7
(July/August 2003): 52-55.
2 Imel, Margo and Campbell James R, "Mapping from a Clinical Terminology to a Classification" AHIMA's 75th Anniversary
National Convention and Exhibit Proceedings, October 2003


## Page 5

code lists, also known as pricelists or charge description masters (CDM) , to the standard
classifications mandated by CHI that will be used to report medical records for diagnoses,
procedures performed, and treatment given for both admitted and non- admitted patient
encounters.

Mapping will aid in the following:

•
Standardization of service descriptions across healthcare to unify reporting

•
Facilitate exchange of information, reimbursement claims, outcome reporting

•
Support VBHC initiatives

•
Improve transparency and sustainability

CHI standards mandated under nphies

Saudi Billing System (SBS):
The SBS was developed by CHI to standardize the classification and description of health care
interventions and services thus facilitating the reporting and billing practices and unifying the
patient records reporting across the national healthcare system. SBS is based on the Australian
Classification for Health Interventions (ACHI) and is compatible with standards and
classifications mandated by Saudi Health Council (SHC) and is the standard code set under the
National Platform for Health and Insurance Exchange (NPHIES)


## Page 6

ADA:
The Australian Schedule of Dental Services and Glossary is published by the Australian Dental
Association (ADA)

Note: Use of ADA codes for OP oral health is a temporary solution. With the introduction of
SBS V2.0, the ADA codes will no longer be utilized. A standard map between ADA 12th Edition
and SBS V2.0 has been created to ease the transition.

SFDA – GTIN:
The GTIN codes are unique codes used for billing drugs and packaged pharmaceuticals adopted
by the SFDA, the regional regulatory authority for food, drugs and medical devices in Saudi
Arabia.

SFDA-GMDN:
The Global Medical Device Nomenclature (GMDN) is a standard list of generic names used for
naming, grouping and identification of medical devices and consumables that are used in the
diagnosis, prevention, monitoring, treatment or alleviation of disease or injury in humans.

RECOMMENDED STEPS FOR MAPPING PROCESS:

Step I: Formation of the mapping team:
Inclusion of resources from different disciplines and departments will ensure that the necessary
skill sets are available for all steps in the mapping process. Recommended team members
include:
a. HIM/Coding
b. Clinical Department /Ancillary Departments
c. RCM/Billing
d. Information Systems
e. Patient Access

Step II: Clean up and preparation
A complete and accurate price list/charge description master is a fundamental step in assuring
that the services provided and coded are present on the bill and submitted on the claim and is
the source of truth for all billable services provided. The typical components of the charge
description master include:
A. Department/Service type/Designation


## Page 7

B. Internal Code
C. Internal Code Description
D. Price
E. Standard Code
F. Standard Description

Clean up of the price list prior to commencing mapping is an essential step and the following
points should be considered:
1. Identify and delete or retire non-used services; i.e., services that have been discontinued
by the organization.
2. Identify duplicated items where the same service is provided by multiple departments.
Duplications should be retired/deleted. See example below.

Example – extracted from a provider price list:

In the price list/service list extract above the procedure “nephrectomy” appears eighteen
(18) times. The recommendation is to represent each distinct nephrectomy procedure
once within the price list, matching the descriptions to the standard classification which in
this case is SBS.

3. Identify all packages. All component items of packages will need to be identified including
operative procedures/interventions, services, drugs, consumables, and devices to ensure
each item is available in the price list
4. Identify all bundled services


## Page 8

5. Identify hard-coded services, i.e., where the code is selected
through an ordering system (CPOE), vs. soft-coded services where the codes are assigned
by the Medical Coders. Examples of hard coded services may include resulted laboratory
tests, pharmaceuticals, medical devices, consumables as well as simple interventions
ordered by physicians. Soft-coded services are usually coded by a medical coder after
reviewing the completed documentation. Examples include operative procedures and
interventional radiology, where the coder must ensure that all coding rules and standards
are applied for accuracy and completeness.

6. Identify incomplete or ambiguous service descriptions and work with the clinical and
ancillary departments for clarification of the service descriptions. The description should
include site, technique and sample nature, if applicable.

The recommended outcome of the mapping exercise is full conversion to the standard
classification(s). However, an organization’s price list is usually linked to many different
provider software programs including those used by clinicians to document procedures
performed and services provided. Usually, the clinician selects a name, term or abbreviation
for the procedure or services, which, is linked to a code. This may necessitate that the map
between the internal and standard codes is maintained indefinitely.

Step III: Mapping

Providers may choose to outsource mapping to a third-party vendor, i.e., RCM Company, or
complete the mapping project using internal resources.

The following services should be mapped:
•
Medical, surgical, laboratory, imaging, dental and services to Saudi Billing System (SBS)
•
Medical devices and consumables and devices to SFDA/GMDN
•
Medicine/pharmaceuticals to SFDA/GTIN
Key Steps for mapping

1. Search for the standard code that matches the description of the non-standard code
2. IF no code matches the description, THEN map to a description with a similar meaning
3. IF no codes with similar meaning exist, THEN map to an unlisted code of the same
category.


## Page 9

Mapping tools and resources:

•
SBS V2.0 Tabular listing (Excel) with inclusion, exclusion notes and guidelines
•
SBS V2.0 Alphabetic Index (PDF)
•
ADA 12th Edition to SBS V2.0 map
•
SFDA/GTIN code list
•
SFDA/ GMDN Codes Lists along with descriptions
•
RCM vendors consulting services for mapping
•
Vendor – Clinical Data dictionaries or mapping engines
•
qCHICodes Query support portal https://chi.accumed.sa:8080/portal
Register for credentials via Support email: sbs.query@accumed.sa
Providers may submit queries for mapping assistance and to validate if services are
unlisted. Guidelines for submission are available on the website.


## Page 10

Guidelines for common challenges:

During the process of mapping, health care provider and insurers may face challenges
mapping in particular circumstances. See the following examples:

1. Use of Packages:
All of the individual component services of the package should be identified using one or
more codes from the standard codes to accurately capture all services performed. For
example, if the package is for a cholecystectomy the main operative procedure, labs,
imaging, consumables, medications would need to be identified.
Providers may need to consider how to link the detailed codes to the order entered by the
physician in the CPOE (code "explosion”) in order to capture all relevant services provided.

Examples:
1-A

Notes:
90467-00-00
Spontaneous vertex delivery
90472-00-00
Episiotomy [1343]
99999-99-99
Unlisted Procedure Code
83600-00-50
Secondary follow up treatment with the same condition within the mandated timelines Consultant
83600-00-00
Office Assessment for diagnosis treatment and counselling a new or established patient by General
Practitioner
73050-35-50
Blood test, thyroid stimulating Hormone (TSH)
73250-00-80
Blood grouping abo
73100-00-90
Complete blood cell count (red cells, white blood cell, platelets), automated test
73250-00-30
Coombs direct antiglobin test
73100-09-50
Coagulation assessment blood test
73100-09-50
Coagulation assessment blood test
73100-09-80
Unlisted hematology and coagulation procedure
16514-01-00
External fetal monitoring
83700-00-00
Unlisted services yet to be defined.
83610-02-70
Room and Board charges of a neonatal ( 0-22 days age) born in the hospital requiring of special
medical attention in special care settings. Charged Per Day
83610-02-70
Room and Board charges of a neonatal ( 0-22 days age) born in the hospital requiring of special
medical attention in special care settings. Charged Per Day
37704
Anaesthesia breathing circuit, single-use
62919
Vascular catheter stylet
63843
Mouth gag, adjustable, single-use
30224
Lactate IVD, kit, reduction/oxidation, rapid
06285108000129 DAFLON 500MG TAB
05702191011685 FUCITHALMIC VISCOUS EYE DROPS
07612791034992 METHERGINE 0.2MG-ML AMPULES
06285111000147 METRONIDAZOLE 500MG/100ML INTRAVENOUS INFUSION
05415062002025 PROSTIN E2 2MG VAGINAL GEL IN APPLICATOR
07612791037887 SYNTOCINON 5 IU injection
06285101001734 XEFO 8MG TAB
06285097000841 ZINNAT
07640149615555 KONAKION MM PAED 2MG-0.2ML AMP
06251107132017 DICLOGESIC
96091-00-00
Manufacture of assistive or adaptive device, aid or equipment
Internal Price List
Map to SBS
073001271
NORMAL DELIVERY
WITH NEWBORN
SCREENING PACKAGE
(SHARED ROOM) -
2DAYS PKG


## Page 11

In the example above, Prostin and Syntocinon – listed with drugs,
therefore the package should also include procedure codes for induction of labor (90465-
xx-00) or augmentation of labor (90466-xx-00)

2. One-to-Many Mappings:
In such cases one provider nonstandard code describes more than one procedure or
service in the standard code set. The recommendation is to unbundle the price list code to
accurately capture all services provided. In the process of unbundling, it is important to
consider existing coding guidelines, where applicable.

Examples:

2-A

In this case, the inclusion notes for 31500-00-01 state that localization of breast (non-
stereotactic) is included with excision of lesion, therefore, the mapping would be revised
as follows.

Revised mapping:

Note: Any additional laboratory or other services included in the package would need to
be confirmed and mapped as well.

2-B

In this case, the mastectomy package procedure is mapped to two SBS codes. The
remainder of the labs, imaging, medications, and services included in the package would
need to be listed and mapped to the appropriate standard codes.

31500-00-01
Excision of lesion of breast, unilateral
31500-00-02
Excision of lesion of breast, bilateral
31536-00-01
Localisation of lesion of breast, unilateral
31536-00-02
Localisation of lesion of breast, bilateral
Map to SBS
73001622
BREAST LUMP EXCISION
WITH WIRE LOCALIZATION -
1DAY PKG
Internal Price List
73001622
BREAST LUMP EXCISION
WITH WIRE LOCALIZATION -
31500-00-01
Excision of lesion of breast, unilateral
Internal Price List
Map to SBS
30336-00-00
Radical excision of lymph nodes of axilla
31518-00-00
Simple mastectomy, unilateral
07300224
UNILATERAL RADICAL
MASTECTOMY - 6 DAY PKG
Internal Price List
Map to SBS


## Page 12

3. Many-To-One mappings:
This scenario involves the mapping of many provider codes to one valid standard code.
Merging or consolidation of duplicate services from different departments is
recommended, with the duplicate items retired or deleted. This will allow the standard
service code to be captured.

Examples:

3-A Bone Densitometry

In this case, the HCP price list contains Bone Densitometry: Two codes are available in SBS
and cover all body sites. Determine if DEXA or CT.

3-B Magnetic Resonance Imaging
In this example, the provider has defined codes for MRI for all body extremities,
including laterality. In SBS however, there are only four codes available, MRI of an
extremity, either with or without contrast medium. For mapping, determine if the MRI
with or without contrast and if unilateral vs. bilateral.

03037001
BONE DENSITOMETRY-BASIC
12306-00-00
Bone densitometry using dual energy x-
ray absorptiometry
03037004
BONE DENSITOMETRY-LUMBAR (NM)
03037006
BONE DENSITOMETRY-WHOLE BODY COMP. (NM)
03037010
BMD-ADVANCED HIP ASSESSMENT
03037011
BMD-BASIC & WHOLE BODY
03037012
BMD-BASIC (LUMBAR + DUAL FEMUR)
03037013
BMD- BASIC (VERTEBRAL HEIGHT ASSESSMENT AP & LAT.)
03037014
BMD-BASIC (VERTEBRAL HEIGHT ASSESSMENT LATERAL)
03037015
BMD-DUAL FEMUR (BOTH)
03037016
BMD-FOREARM
03037017
BMD-LUMBAR SPINE (VERTEBRAL HEIGHT ASSESSMENT AP
& LAT)
03037018
BMD-LUMBAR SPINE (VERTEBRAL HEIGHT ASSESMENT
LATERAL)
03037019
BMD-LUMBAR SPINE ONLY
03037020
BMD-TOTAL HIP REPLACEMENT (EXCLUDING PROSTHESIS)
03037021
BMD-WHOLE BODY
03037023
BMD- WHOLE BODY COMPOSITION/FAT/BONE/MUSCLES
03037025
VERTEBRAL HEIGHT ASSESSMENT AP & LATERAL
03037026
VERTEBRAL HEIGHT ASSESSMENT LATERAL
03037027
BMD-WHOLE BODY COMPOSITION BONES
03037005
BONE DENSITOMETRY-SPINE (SPL. OFFER)
03037008
BONE DENSITY-F/ARM,FEMUR,LUMBAR[DR.COOKE-SPL]
03037022
BMD-WHOLE BODY + BODY COMPOSITION
03037028
BMD-WHOLE BODY COMPOSITION FAT
03037029
BMD-WHOLE BODY COMPOSITION MUSCLES
Internal Price List
Map to SBS
12309-00-00
Bone densitometry using quantitative
computerised tomography


## Page 13

3-C
In the following examples, all three of the non-standard descriptions map to one SBS
procedure code. The remainder of the services provided, that differentiate the packages,
will need to be identified from laboratory, imaging and service codes.

3-C-1 Sialadenectomy

3-C-2 Cataract removal with lens insertion

Note: Code also IOL insertion when performed. 42703-00-xx, 42701-00-xx

4. Bundled Services and Labs:
Where provider codes are bundled for labs and other services the recommendation is to
unbundle the services included in the code descriptions in order to accurately capture all
lab tests performed, unless an appropriate lab profile has already been defined in SBS.

Examples:

4-A Thyroid Hormones

73050-35-50
Blood test, thyroid stimulating Hormone (TSH)
73050-36-50
Measurement of free triiodothyronine (T3)
73050-35-30
Measurement of free thyroxine
Internal Price List
Map to SBS
02012025 THYROID HORMONES PACKAGE (TSH, FT3,
FT4)-PKG.


## Page 14

4-B Cardiac Enzymes

•
Review of SBS, reference search reveals an existing code for the Troponin I.

Revised mapping:

5. Incomplete/Ambiguous Service Descriptions:
All ambiguous or incomplete service descriptions require a review and validation, and
possible update by the appropriate stakeholder team, to determine whether or not the
descriptions are valid procedure, interventions, consumables or drugs. The internal code
descriptions may be updated, if necessary, and then should either be mapped to the
correct standard codes and descriptions or deleted from the provider price list.
Examples:

5-A Limb lengthening

•
Is the limb lengthening bipolar or one cut?
•
Clarification required for “Equinox correction.” Is this a boney deformity, or should it be
Equinas correction (tendon)?

5-B In the following example, the description is not clear. Is this General Anesthesia?
This item should be reviewed with the clinical team to clarify the service description

73050-09-40
Measurement of Creatine kinase; total; blood
73050-09-50
Measurement of Creatine kinase mb
isoenMeasurement ofyme; blood
(unlisted codes) Troponin I
73050-35-90
Measurement of aspartate amino transferase (AST)
(SGOT)
02011112 CARDIAC ENZYMES PACKAGE (CPK, CPKMB,
TROPONIN I AST )
Internal Price List
Map to SBS
73050-09-40
Measurement of Creatine kinase; total; blood
73050-09-50
Measurement of Creatine kinase mb
isoenMeasurement ofyme; blood
73050-36-70
Quantitative Measurement of muscles Tissues troponin
73050-35-90
Measurement of aspartate amino transferase (AST)
(SGOT)
Internal Price List
Map to SBS
02011112 CARDIAC ENZYMES PACKAGE (CPK, CPKMB,
TROPONIN I AST )
50303-00-00
Limb lengthening (excludes bipolar) [1578]
50306-00-00
Limb lengthening ,bipolar [1578]
90604-00-00
Correction of bony deformity
Internal Price List
Map to SBS
07300740
TIBIA LENGTHENING WITH
EQUINOX CORRECTION-
1DAY PKG.
89057
Intervention / GA
Internal Price List
Map to SBS


## Page 15

6. No Match for Code Description
When no match can be found in the standard code descriptions for a service, the
description should be reviewed for accuracy or additional detail or description from the
clinical or ancillary departments. If there is still no match, the service may be assigned an
unlisted code from the appropriate category. Refer to the section on unlisted codes.

6-A Laparoscopic procedures

The following procedure performed laparoscopically does not have a specific laparoscopic
code and was mapped to the unlisted procedure code.

A review of the existing ACS standard (ACS 0023) for Laparoscopic / Arthroscopic /
Endoscopic Surgery: If a procedure is performed laparoscopically, arthroscopically or
endoscopically, and there is no code provided which encompasses both the endoscopy
and the procedure, then both procedures should be coded

In this case one of the following nephrolithotomy codes may be assigned, as appropriate,
with the addition of the Laparoscopy code

6-B FESS-Functional Endoscopic Sinus Surgery

Providers have mapped FESS to an unlisted code.

However, due to the nature of FESS, there is no one code that may be used to represent
the services provided, along with the 41764-01 [370] Sinoscopy to indicate the endoscopic
nature of the surgery.
073001143
LAPAROSCOPIC NEPHROLITOTOMY-4
DAY PKG
99999-99-99
Unlisted Procedure Code
73001166
LAPAROSCOPIC NEPHTOLITHOTOMY-
4 DAYS PKG
99999-99-99
Unlisted Procedure Code
Internal Price List
Map to SBS
36540-00-01
Nephrolithotomy with removal of <= 2 calculi, unilateral
36540-00-02
Nephrolithotomy with removal of <= 2 calculi, bilateral
36543-00-01
Nephrolithotomy with removal of >= 3 calculi, unilateral
36543-00-02
Nephrolithotomy with removal of >= 3 calculi, bilateral
30390-00-00
Laparoscopy
Internal Price List
Map to SBS
73001166
LAPAROSCOPIC
NEPHROLITHOTOMY -4 DAYS PKG
073001287
LIMITED FESS-1DAY PKG
99999-99-99
Unlisted Procedure Code
Internal Price List
Map to SBS


## Page 16

According to Australian Coding Standards (ACS 0807), FESS may include a variety of
procedures performed, in any combination, therefore only the appropriate codes should
be assigned. The procedures may include the following:
41716-01 [387] Intranasal maxillary antrostomy, unilateral (includes formation of an antral meatal window)
41716-02 [387] Intranasal maxillary antrostomy, bilateral (includes formation of an antral meatal window)
41716-00 [383] Intranasal removal of foreign body from maxillary antrum
41737-02 [386] Ethmoidectomy, unilateral
41737-03 [386] Ethmoidectomy, bilateral
41731-00 [386] Ethmoidectomy, frontonasal approach
41731-01 [386] Ethmoidectomy with sphenoidectomy, frontonasal approach
41737-09 [386] Frontal sinusectomy
41746-00 [386] Radical obliteration of frontal sinus
41752-01 [386] Sphenoidectomy
41716-05 [384] Biopsy of maxillary antrum
41752-04 [384] Biopsy of sphenoidal sinus
41737-07 [384] Biopsy of frontal sinus
41737-08 [384] Biopsy of ethmoidal sinus

Where FESS is documented, 41764-01 [370] Sinoscopy must also be used to indicate the
endoscopic nature of the surgery.

6-C Shoulder Replacement

In the following example, the HCP has mapped reverse shoulder replacement to an
unlisted code.

However, research on the procedure name indicates that a reverse shoulder replacement
is a total arthroplasty of the shoulder and would be mapped to either of the following
codes following the SBS alphabetic index:

6-D Revision Procedure for Bariatric Surgery

An HCP mapped this procedure to unlisted code as there is no code that is specific for the
revision of laparoscopic sleeve gastrectomy.

073001504
REVERSE SHOULDER
REPLACEMENT - 3DAYS PKG
99999-99-99
Unlisted Procedure Code
Internal Price List
Map to SBS
48918-00-01
Total arthroplasty of shoulder, unilateral
48918-00-02
Total arthroplasty of shoulder, bilateral
Internal Price List
Map to SBS
REVERSE SHOULDER
REPLACEMENT - 3DAYS PKG
073001504
073001681
REDO LAPAROSCOPIC SLEEVE
GASTRECTOMY - 1DAY PKG
99999-99-99
Unlisted Procedure Code
Internal Price List
Map to SBS


## Page 17

A review of the SBS alphabetical index and Tabular list reveals a specific code for the
revision of a bariatric procedure along with instructions for coding. Following the
instructional note at 30514-01-00 [889] Revision procedure for obesity, assign first a code
for the obesity procedure performed, followed by 30512-03-00 [889] Laparoscopic gastric
bypass
Make note of the following inclusion terms that have been added to 30514-01-00 [889] in
the SBS Tabular List, to help clarify the code assignment:
Revision (reoperation) of:
•
Biliopancreatic diversion
•
Duodenal jejunal bypass
•
Gastric bypass
•
Gastroplasty
•
Ileal interposition
•
Sleeve gastrectomy
Therefore, the revision of a laparoscopic sleeve gastrectomy would be mapped as follows:

6-E D&C (Dilatation and Curettage) with Polypectomy – two procedure package

In this example a single code is not available for the D&C plus polypectomy, and the HCP
mapped the package to an unlisted code:

Revised mapping:

This package required one to many mapping where both the D&C and the polypectomy
are required to fully describe the procedure.

30511-09-00
Laparoscopic sleeve gastrectomy [LSG]
30514-01-00
Revision procedure for obesity
Internal Price List
Map to SBS
073001681
REDO LAPAROSCOPIC SLEEVE
GASTRECTOMY - 1DAY PKG
35640-00-00
Dlation and curretage of uterus [D&C]
35633-01-00
Polypectomy of uterus via hysteroscopy
Internal Price List
Map to SBS
07300817
D & C WITH POLYPECTOMY PKG.


## Page 18

7 Pharmaceutical and Consumables/Devices

7-A Pharmaceuticals
Multiple GTIN codes may be available for the same SFDA registration code and should be
counted as the same unless there is a recall or suspension for a specific GTIN.

7-B Consumables/Devices
If a GMDN code is not available for a device or consumable, the existing SFDA registration
code may be used. If neither GMDN nor SFDA codes are available, the appropriate
unlisted codes shall be utilized.

Step IV: Validation
Completed mapping, whether performed by the internal team or a 3rd party vendor,
should be reviewed and validated by the clinical teams.
• Do the descriptions of the standard codes match, or describe the same
procedures as described by the non-standard codes?
• Are all of the services provided by each department available in the mapped
price list?
The mapping will also be validated by the payers.

Step V: Maintenance

The mapping of the price list to the standard code set is not a "one and done” project.
The price list or charge description master will require review and update as an ongoing
process. Provider service lines may be added or deleted and/or the standard
classifications will be updated to reflect changes in medical practice and introduction of
new technologies through the addition, modification or deletion of codes. This will
necessitate a thorough review of the price list to ensure new services are added and older
services are retired.

Establishing a maintenance process should consider the following components:

1. Review cycle – establish quarterly or annually, at a minimum.
2. Responsibility for maintenance of the price lists should be delegated to a designated
team, including the final approval of changes.
3. Process for review and validation of descriptions of new services to ensure they fully
describe the service provided and that the descriptions match the standard codes,
including an indication of the site, technique and sample nature, where applicable.


## Page 19

4. Review of new/modified/deleted standard codes to determine if the service is offered
by the provider and the changes are reflected in the price list per the effective date.

Since the price list or charge description master is the source of truth for all billable
services provided, it is essential that only services offered by the provider are included.
This will ensure that inappropriate services are not reported and subsequently denied. For
example, if a provider does not perform transplants, then transplant codes should not be
reflected in the provider price list.
UNLISTED CODES
According to the Standards and Guidelines of CCHI Billing System and the Saudi Billing System
Coding Standards (SBSCS), unlisted code(s) are restricted to be only used for the services that
are not available in the SBS Tabular List. However, on submission of the claim the service
specification and details should be mentioned.3

Unlisted codes help expedite and finalize the coding, billing, and reimbursement processes in
situations where an unlisted code is the only option for reporting certain services or procedures
performed by the provider, for example, advancements in medical science, including new
procedures, technology, and devices introduced prior to code expansion. 4

The nphies Shadow Billing Guidelines5 recommend that medical devices and consumables,
medications and outpatient dental codes that cannot be mapped to a corresponding GMDN,
SFDA-GTIN, or ADA code should be mapped to a similar code, and the non-standard code and
description should be included in the transaction to maintain the granularity level and detail. If
the item cannot be mapped to a similar code, it should be mapped to the unlisted code for the
category. At the same time, the services or items that cannot be mapped must be reported to
CHI along with a complete description of the item/service.

The table below lists all of the available codes that may be used for mapping procedures,
services, drugs/medications and medical devices that do not have an existing code.

New categories have been added for the reporting of unlisted drugs and consumables/devices
in order to better track the items and report issues back to the SFDA.

Note: It is essential that unlisted services are mapped to the correct unlisted code category.

3 Introduction to the Standards and Guidelines of CCHI Billing System, CCHI-BS V0.2a beta, 07 June 2020.

4 www.fortherecordmag.com/archives/1018p28.shtml

5 nphies Shadow Billing Guidelines v1.5, 1st June 2021


## Page 20

For example,
•
pharmaceuticals and devices
-
do map to 99999999999999*
-
do not map to 83700-00-00 Unlisted Services not yet defined.
Table of Unlisted Codes
Unlisted Code
Long description
TYPE
97089-00-10
Unlisted oral medicine/ oral pathology procedure
Dental Services (SBS)

97179-00-10
Unlisted preventive dental procedure
Dental Services (SBS)
97399-00-10
Unlisted oral surgery procedure
Dental Services (SBS)
97459-00-10
Unlisted restorative or endodontic procedure
Dental Services (SBS)
97789-00-10
Unlisted prosthodontic procedure
Dental Services (SBS)

97879-00-10
Unlisted orthodontic procedure
Dental Services (SBS)

97989-00-10
Unlisted adjunctive dental service
Dental Services (SBS)

99999-99-92
Unlisted imaging procedure
Imaging services (SBS)
73050-39-70
Unlisted chemistry procedure
Laboratory & Pathology (SBS)
73050-60-60
Unlisted Immunoassay detection with direct visual observation
Laboratory & Pathology (SBS)
73050-61-60
Unlisted microbiology procedure
Laboratory & Pathology (SBS)
73100-27-21
Unlisted assay for Virus Antibodies
Laboratory & Pathology (SBS)
73100-09-80
Unlisted Haematology procedure
Laboratory & Pathology (SBS)
73100-18-20
Unlisted antigen delayed type hypersensitivity (DTH) test
Laboratory & Pathology (SBS)
73100-22-00
Unlisted assay for Fungus Antibodies
Laboratory & Pathology (SBS)
73100-25-50
Unlisted assay for Protozoa Antibodies
Laboratory & Pathology (SBS)
73150-01-20
Unlisted urinalysis procedure
Laboratory & Pathology (SBS)
73200-03-60
Unlisted cytopathology procedure
Laboratory & Pathology (SBS)
73200-06-30
Unlisted cytogenetic study
Laboratory & Pathology (SBS)
73200-10-60
Unlisted surgical pathology procedure (histo-diagnostic procedure)
Laboratory & Pathology (SBS)
73250-03-80
Unlisted blood bank procedure (transfusion procedure)
Laboratory & Pathology (SBS)
73300-03-70
Unlisted Quantitative Therapeutic Drug Test
Laboratory & Pathology (SBS)
73350-06-00
Unlisted molecular diagnostic procedure
Laboratory & Pathology (SBS)
73400-00-40
Unlisted in vivo laboratory procedure
Laboratory & Pathology (SBS)
73400-01-50
Unlisted clinical pathology procedure
Laboratory & Pathology (SBS)
73400-05-10
Unlisted assisted reproduction procedure (male or female)
Laboratory & Pathology (SBS)
83500-00-80
Unlisted ambulance service
Ambulance & Transportation (SBS)
83700-00-00
Unlisted services yet to be defined
KSA Service codes (SBS)
99999-99-99
Unlisted ambulatory service
No chapter assignment (SBS)
99999
Unlisted Code-Medical Devices
SFDA_GMDN/SFDA Registration ID
99999999999991
Unlisted Code-Nutritional Supplements (Other nutritional
substitute)
SFDA_GTIN/SFDA Registration ID
99999999999992
Unlisted Code-Nutritional Supplements (Enteral feeds)
SFDA_GTIN/SFDA Registration ID
99999999999993
Unlisted Code-Other Non-Medication
SFDA_GTIN/SFDA Registration ID
99999999999994
Unlisted Code-Nutritional Supplements (Mother's milk substitute
(baby/infant formula)
SFDA_GTIN/SFDA Registration ID


## Page 21

99999999999995
Unlisted Code-Cosmetic
SFDA_GTIN/SFDA Registration ID
99999999999996
Unlisted Code-Herbal & Vitamins
SFDA_GTIN/SFDA Registration ID
99999999999997
Unlisted Code-OTC
SFDA_GTIN/SFDA Registration ID
99999999999998
Unlisted Code-Chemotherapy
SFDA_GTIN/SFDA Registration ID
99999999999999
Unlisted Code-Other Medications
SFDA_GTIN/SFDA Registration ID

In some cases, drugs that are not registered for use in Saudi Arabia may be approved by the
SFDA for importation and limited use in emergency cases. 6 In this event, the medication is not
assigned a GTIN or SFDA registration number. For claiming purposes, the authorized facility or
entity may map the pharmaceutical to the appropriate Unlisted Drug code category and
provide supporting information in the form of the CR#, or reference number, as text along with
a copy of the approval document as a .PDF or image file in order that the payer will have all of
the required documentation for validation purposes.
SBS MAINTENANCE:

CHI maintains the SBS code sets as the custodian of the classification. CHI welcomes the
engagement of all healthcare providers and payers to participate in improving the SBS,
including all sectors and specialties, through the official channels provided by CHI in order to:

1. Review of any reported issues in implementing the SBS that may require modification of service
descriptions or more details added to existing classifications
2. Evaluate submissions for new services that are not available in SBS and are recognized as valid
services to be added to future releases
3. Support health care providers and/or payers in the correct implementation of the SBS.
An on-line platform “qCHIcodes”, has been created to facilitate the queries and submissions for
the implementation and continued maintenance of the SBS. In the first phase, providers and
payers may submit mapping and coding queries and track the status and support on the
implementation of the SBS while the second phase will cover the submissions for the creation
of new codes, revisions of descriptions or deletions of codes as well as indexing requirements.

The link for the portal: https://chi.accumed.sa:8080/portal

Register for credentials via Support email: sbs.query@accumed.sa

6 https://www.fdanews.com/ext/resources/files/05-15/5-15-SFDA-1.pdf?1520912020


## Page 22

PROVIDER-PAYER MAPPING VALIDATION PROCESS:

During the Shadow Billing timeframe, Payers are able to validate the Provider mapping as both
the standard codes and the non-standard codes will be reported on the claim in nphies. 7
In addition, once the provider completes mapping their full price list to the standard codes the
price list will be submitted to the payers as part of the onboarding process:

• The payer will review and accept the provider’s mapped codes within five (5) working
days.
• If the payer has any reservations or objections on the mapping of the pricelist, then the
identified issues should be validated and updated by the provider within three (3) working
days.
•
The revised mapping will be reviewed, confirmed and accepted by the payer within (3)
working days.
• Any mapping disputes that are not resolved following the above process shall be
escalated to CHI.

If the provider mapped pricelist is approved by two (2) payers, then the mapping should be
accepted by any subsequent payer. In the event that any further disputes arise, they should be
resolved following the same process mentioned above. Any unresolved disputes may be
reported to CHI.
PAYER VALIDATION KPI:

The payer performance on validation of all provider mapping will be monitored and presented
in the nphies dashboard.

7 nphies Shadow Billing guidelines Version 1.5 , 1st June 2021
