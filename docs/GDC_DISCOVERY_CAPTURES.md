# GDC discovery capture register

Evidence collected 2026-09-24 UTC for baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`.
Interpretation and admission decisions: [GDC strategy](GDC_STRATEGY.md).
Local capture root: `C:/Users/Rahul Khatri/AppData/Local/Temp/ontojev-architecture-20260924/`.
Each numbered `NNN.body` has full bytes; `ledger.json` records canonical request parameters/body,
full URL, method, timestamps, status, headers, byte count, body and request SHA-256, latency and outcome.
These files are outside production data and are not portable committed fixtures. Preserve them before
temporary-directory cleanup if implementing the fixture gate. No provider response has been represented
as a committed test fixture.

Campaign wall-clock window: **2026-09-24 18:08:13.121640 UTC through 18:20:09.608368 UTC**.
Ledger SHA-256: `fc5ddcb2d0c4981e500dac5d6b7ed04dd7676c4f6911040d21076784b2fb4225`.
Final offline verification matched all 69 body hashes and byte lengths to the ledger. Per-request
timestamps preserve their original timezone offset; response Date, Content-Type, Content-Length
(when supplied) and other headers remain in each ledger entry. The ledger itself is local evidence,
not an application event log. Body timings exclude documentation analysis between sessions.

All 69 attempts ended COMPLETE/HTTP 200; total 6,093,958 bytes. This describes HTTP-body completion,
not scientific completeness of partial search pages. No retries, redirects, authentication or downloads.
The request hash is SHA-256 of canonical JSON of the recorded audit specification (including query/page
metadata), NOT the runtime transport's normalized-request hash. Body SHA-256 is directly comparable.

## Reproducible request specifications

Base `https://api.gdc.cancer.gov`; GET unless expression POST. URL query encoding is standard percent
encoding. Headers: Accept */*, Accept-Encoding identity, Content-Type application/json and anonymous
OntoJev audit User-Agent. No authentication. No redirect following.

Filter shorthand `IN(field,values)` means
`{"op":"in","content":{"field":field,"value":values}}`; AND is
`{"op":"and","content":[...]}`. Query filters are compact JSON strings.

- 001 GET /status. 002–011 GET /{projects,cases,files,genes,ssms,ssm_occurrences,cnvs,cnv_occurrences,segment_cnvs,segment_cnv_occurrences}/_mapping in that order.
- 012 /projects: IN(project_id,[TCGA-LUAD]), size 1, fields project_id,name,summary.case_count,summary.file_count.
- Case manifest C: 013/026/027 /cases, IN(project.project_id,[TCGA-LUAD]), size250, from0/250/500,
  sort case_id:asc, fields case_id,submitter_id,project.project_id. 013 additionally requested
  available_variation_data, which produced an unrecognized-field warning; it is not admitted.
  Concatenate returned case_id in page order; assert 585 unique and sorted.
- Gene manifest G: 014/028–036 /genes, IN(biotype,[protein_coding]), size100, from0..900 by100,
  sort gene_id:asc, fields gene_id,symbol,biotype. Assert 1,000 unique and sorted; reported total 19,843.
- 015 /ssms size 2, IN(occurrence.case.project.project_id,[TCGA-LUAD]); fields
  ssm_id,chromosome,start_position,end_position,ncbi_build,reference_allele,tumor_allele,consequence.transcript.gene.gene_id.
- 016 /ssm_occurrences size2; AND(case.project.project_id=TCGA-LUAD,
  ssm.consequence.transcript.gene.gene_id=ENSG00000141510). fields ssm_occurrence_id,case.case_id,
  case.project.project_id,ssm.ssm_id,ssm.consequence.transcript.gene.gene_id,case.observation.
  The last broad field produced a warning. 052 repeats the filter, replacing fields with
  ssm_occurrence_id,case.case_id,case.observation.sample.tumor_sample_uuid,
  case.observation.variant_calling.variant_caller,case.observation.read_depth.t_depth,
  ssm.ssm_id,ssm.consequence.transcript.gene.gene_id.
- 017 /cnvs size5; AND(occurrence.case.project.project_id=TCGA-LUAD,
  consequence.gene.gene_id=ENSG00000141510); fields cnv_id,cnv_change,cnv_change_5_category,
  gene_level_cn,consequence.gene.gene_id,ncbi_build.
- 018 /cnv_occurrences size5; AND(case.project.project_id=TCGA-LUAD,
  cnv.consequence.gene.gene_id=ENSG00000141510). Broad case.observation field was warned.
  050/051 acquire this complete logical query with size250, from0/250, sort cnv_occurrence_id:asc,
  fields cnv_occurrence_id,case.case_id,case.project.project_id,case.observation.copy_number,
  case.observation.sample.tumor_sample_uuid,case.observation.sample.tumor_sample_barcode,
  case.observation.src_file_id,case.observation.variant_calling.variant_caller,
  case.observation.sample_ploidy_integer,cnv.cnv_id,cnv.cnv_change,cnv.cnv_change_5_category,
  cnv.consequence.gene.gene_id.
- 019 /segment_cnvs size 2, IN(occurrence.case.project.project_id,[TCGA-LUAD]), default fields.
  020 /segment_cnv_occurrences size 2, IN(case.project.project_id,[TCGA-LUAD]); fields
  segment_cnv_occurrence_id,case.case_id,case.project.project_id,case.observation,segment_cnv;
  broad fields warned. 053 uses leaf fields segment_cnv_occurrence_id,case.case_id,
  case.observation.copy_number,case.observation.sample.tumor_sample_uuid,case.observation.src_file_id,
  segment_cnv.chromosome,segment_cnv.start_position,segment_cnv.end_position,
  segment_cnv.cnv_change,segment_cnv.cnv_change_5_category.
- 021 /files size5; AND(cases.project.project_id=TCGA-LUAD,access=open,
  data_type=Gene Expression Quantification); fields file_id,access,data_type,analysis.workflow_type,
  cases.case_id,cases.samples.sample_id,cases.samples.sample_type,
  cases.samples.portions.analytes.aliquots.aliquot_id.
- 022 /analysis/top_mutated_genes_by_project size 5, IN(case.project.project_id,[TCGA-LUAD]).
  023 /analysis/mutated_cases_count_by_project size0, no filter.
- 024 /cases size 2, sort case_id:asc, project filter; fields case_id,demographic.vital_status,
  demographic.days_to_death,diagnoses.days_to_last_follow_up,diagnoses.age_at_diagnosis,
  diagnoses.ajcc_pathologic_stage,samples.sample_id,samples.sample_type.
- 025 /files size1; AND(cases.project.project_id=TCGA-LUAD,access=open,experimental_strategy=scRNA-Seq);
  fields file_id,data_type,experimental_strategy,analysis.workflow_type.
- 037–046 /analysis/top_cases_counts_by_genes with query parameter gene_ids=comma-joined G[100*i:100*(i+1)], i0..9;
  no fields/format. 047–049 POST /gene_expression/{availability,gene_selection,values}, body
  case_ids=C[:250], gene_ids=G[:100]. Selection adds selection_size100; values adds
  tsv_units=uqfpkm,format=tsv.
- 054 GET /analysis/survival; filters=[{"op":"=","content":{"field":"cases.project.project_id","value":"TCGA-LUAD"}}].
- 055 /cnv_occurrences size0, LUAD case.project filter, facets cnv.cnv_change,cnv.cnv_change_5_category.
- 056–064 POST /gene_expression/values: C[:250], G[100*i:100*(i+1)] for i1..9, uqfpkm/tsv.
  065/066 same values endpoint with G[:100], C[250:500]/C[500:585].
- 067 /cnv_occurrences size2; AND(case.project.project_id=TCGA-LUAD,
  cnv.consequence.gene.gene_id=G[:100]); fields cnv_occurrence_id,case.case_id,
  cnv.consequence.gene.gene_id,cnv.cnv_change.
- 068 /files size 1, AND(file_id=4dc9b096-bc5e-426e-9b5f-965af258239e,access=open),
  same field list as 021. 069 /cases size 1, case_id=cbfef004-b437-4d51-9d88-a2db50aa6481,
  fields case_id,samples.sample_id,samples.sample_type,samples.portions.analytes.aliquots.aliquot_id.

Exact original JSON remains in ledger.json; manifest reconstruction against a later release may differ
and must not be called identical replay. No repeated query was an automatic retry: small probes,
complete targeted queries and differently scoped scaling experiments were separate declared workloads.

## Capture hashes

| ID | Session | Endpoint | Bytes | ms | Body SHA-256 |
|---|---|---|---:|---:|---|
| 1 | mappings | /status | 221 | 1390 | `a8b1c69f9cfc678486e1c897aee6d878f47fab9cb4c60eb6818598bbe30a7139` |
| 2 | mappings | /projects/_mapping | 5036 | 1174 | `abf2586e87e851eadd51a2f3f02fca529b8038b8dd49e90324b070622485f9f4` |
| 3 | mappings | /cases/_mapping | 284276 | 2990 | `4e5fd1736d2b5a17f6cd66929953a6893f4858a0a480480faa26ccafd2e798c8` |
| 4 | mappings | /files/_mapping | 150318 | 2335 | `4b2df18cdfeb5beb8128b9e0c0b97c2fbb3aa50c27a8a07cb05156340b98b22b` |
| 5 | mappings | /genes/_mapping | 90076 | 1896 | `eb8eedde9d1cb0dfae274e85d973fb9de81dafb7243b09d5bacd79b547c200ce` |
| 6 | mappings | /ssms/_mapping | 86999 | 1871 | `be2b71ded0967fcc06ef8a740cd7dd19c46b574ef8261261160772fadb506f15` |
| 7 | mappings | /ssm_occurrences/_mapping | 87318 | 1922 | `bf5c0c6c5446ce6464938cb313f5cc6e5b364272770acb15d68ea09480927b63` |
| 8 | mappings | /cnvs/_mapping | 67151 | 1722 | `3c751187ccf305500c595598beeba5558b744b1a60371aa33b564e56a0e57414` |
| 9 | mappings | /cnv_occurrences/_mapping | 65397 | 1576 | `c82b9d58b20e8d5b3ac73993bd3e4a13aeceaee2c2df67a8ea27ef71c551148c` |
| 10 | mappings | /segment_cnvs/_mapping | 70903 | 1760 | `673fd5b93a1c686d3b43b19104d73e5c53753f7473eb6516981b9ec27f8e76b2` |
| 11 | mappings | /segment_cnv_occurrences/_mapping | 68907 | 1516 | `f46f866c598c825b93895da3cbc5dd3a0845a3c57758e56a76246c61c26de473` |
| 12 | small | /projects | 265 | 1074 | `6128d52e9448c5b657d90511c0d55c89231df24a6ac54430aaa3c78212ef3145` |
| 13 | small | /cases | 42952 | 2314 | `fdddb2a37a5d7ed6123942486430d1728d84abcfd3651ada311080a8bfb46917` |
| 14 | small | /genes | 10664 | 1131 | `c6e6e632674c23df2a5b955b2f9d15166a3c93aca9eb50d560a7a701976fd3dc` |
| 15 | small | /ssms | 1073 | 1086 | `aeb141eb15f9e142896008290b51d557f83531a912f206d7b400a9428e600d93` |
| 16 | small | /ssm_occurrences | 3776 | 1242 | `dab7403f43e32996b544018022679473b8b511a02c4c2ae4440c47e3727cd105` |
| 17 | small | /cnvs | 919 | 1822 | `451eaf1188791a600604edd7e41faeff2cb96685edb7b2fb78090a9c22352f71` |
| 18 | small | /cnv_occurrences | 2217 | 1178 | `d84ec9a8812f5b86c8dc3f8a12c6eebda1c77dd12c842553096ac74fa9fafeb2` |
| 19 | small | /segment_cnvs | 648 | 1117 | `3b9d53cbbd1ac28d98cdfcc75293fad59795856985882672059740fcb5704b34` |
| 20 | small | /segment_cnv_occurrences | 641 | 1244 | `0ac97c9350c2f4e1208ed45327021f2c7212d307292d41f397337298e0c34489` |
| 21 | small | /files | 2527 | 1180 | `2700b5693e8021a5fdffa675752b02838ec2ce60b7a58b767483ac6cdf0c1fd0` |
| 22 | small | /analysis/top_mutated_genes_by_project | 5282 | 1142 | `04205ff85d17f1f6c93ffd142377ff11fd17eae27b8e7c82d4f63c671f06600d` |
| 23 | small | /analysis/mutated_cases_count_by_project | 10825 | 1116 | `cb2a340ca9a843d5009314dd94b78c9f879291821a99743e60e519176d2c4370` |
| 24 | small | /cases | 1213 | 1084 | `1e751bed2f1176738df0a05d692580c0a55694d488645d32f34254a512ffc1c8` |
| 25 | small | /files | 135 | 1068 | `9f3c351f3f05a6b9c5274a23cc1d4589bd73376e3527fa35c6e6077dd061fb71` |
| 26 | scale-inventory | /cases | 42895 | 2485 | `5ef03b2d7f8a1221041c3873ecbe16feb3059d54c8b40eab0b082fea47942021` |
| 27 | scale-inventory | /cases | 14679 | 1415 | `549cfe5783bab618a9688494b8c7f60fb2189eee508d635cf0295c8cdf3dd92a` |
| 28 | scale-inventory | /genes | 10688 | 1275 | `a4e37a44a081e3bb855dc9f79459aa4ee0ad60e31e5bf6137f2d948f8a1d7607` |
| 29 | scale-inventory | /genes | 10666 | 1221 | `f9fd0629398e1148c773311e561d16a80474066943ac1a15123bc3ec5144f0cc` |
| 30 | scale-inventory | /genes | 10680 | 1200 | `0bf6b68fa65b078a482b502355b321c861ff289dd1f9f518b3de6c4466ec768c` |
| 31 | scale-inventory | /genes | 10681 | 1212 | `b69a935bef68ce78a34a1b077c86827903934a07d45ec16bb639c4eb95cadbbb` |
| 32 | scale-inventory | /genes | 10659 | 1118 | `666265aa83d37e1f86928e3077c6ffa99869970d4ecf8b18ddda3857bb5dc32c` |
| 33 | scale-inventory | /genes | 10681 | 1362 | `73e06c6e3825089e3cc89ad393e9779b38296d48a5b6a0f26cf4d8aed5f5075f` |
| 34 | scale-inventory | /genes | 10685 | 1654 | `3e805d495950ddef390a054b75dc8b987aa77e2c4c4fdf6cf5acc7a30d47d625` |
| 35 | scale-inventory | /genes | 10658 | 1412 | `1eb69209ecb1332cd372d495d5b0b8cc4202e2cec3b3da7928f560285b59bb1c` |
| 36 | scale-inventory | /genes | 10677 | 1216 | `7c5f94f2a20e5c008d6ccea7e0a33e987357fc43badb46a0b7412f56f9dc3490` |
| 37 | scale-counts | /analysis/top_cases_counts_by_genes | 246042 | 2771 | `06785e2bb11fb490609bd603a72e2b554987784d82efa39878272b465d5307f8` |
| 38 | scale-counts | /analysis/top_cases_counts_by_genes | 251069 | 3056 | `03a922d5bcbe0132561d8f0a9b071fc3e5768e8d9da822c1e2f86a77caf3b040` |
| 39 | scale-counts | /analysis/top_cases_counts_by_genes | 255174 | 2786 | `d107cd1ee8fbadb193aeb6ce4af752795a663a9443ef0bd140e4c2ef0f2cd964` |
| 40 | scale-counts | /analysis/top_cases_counts_by_genes | 246612 | 3018 | `09da88a91db53331d585ff0adb18d4113f54de5ee5436766179c0d4cd93cce9b` |
| 41 | scale-counts | /analysis/top_cases_counts_by_genes | 255052 | 3156 | `0f83e5f4c99003314732f06144b549348f0d3004e7e93ee49a36b961e3fc2acd` |
| 42 | scale-counts | /analysis/top_cases_counts_by_genes | 256499 | 2988 | `93e72c425f175c95f11991c9ae3fda1e3866723af90ca04f54fef47159bfc2f6` |
| 43 | scale-counts | /analysis/top_cases_counts_by_genes | 245895 | 3076 | `8d53804a7ab9220732722c19d713fe497f7b532e4d12a11723a77a209b72967b` |
| 44 | scale-counts | /analysis/top_cases_counts_by_genes | 256342 | 2692 | `50bc00f0bc90c853cf1b370d2cbc42b38f1254644b6bdb46100076b9c5981447` |
| 45 | scale-counts | /analysis/top_cases_counts_by_genes | 255412 | 2551 | `1c19af18314addfd6775b3849d22e6ac84ea17604ff0414869d224f709898bfe` |
| 46 | scale-counts | /analysis/top_cases_counts_by_genes | 255764 | 2325 | `73365aca2ffe9b521a8a6995a67d9686a40865805630b3a8330e98aec5acf58a` |
| 47 | scale-expression | /gene_expression/availability | 27868 | 1316 | `496d38b4b7a01299a3a95e4f8d1d40c608f331a06a19065915a15dbac196119d` |
| 48 | scale-expression | /gene_expression/gene_selection | 9840 | 1815 | `ba8f8aa0e38a714a0c984f4de0961a36b2888d39b495c425317f75f9802a8a33` |
| 49 | scale-expression | /gene_expression/values | 176337 | 2246 | `5b7fd3e05561c89da46cb785c819325e17abfdab5ac27000ea337a7846a50a4c` |
| 50 | joins | /cnv_occurrences | 138172 | 2058 | `2e48dcb49292aec9e4b23a8a20457b7470ab56af2d7214c725df71f57ac8bef1` |
| 51 | joins | /cnv_occurrences | 7872 | 1115 | `6dbb12ba1101cf58872092b7d9015d70857c8c2bbeea87852b183ab6c9908a86` |
| 52 | joins | /ssm_occurrences | 4611 | 1086 | `dc511e1d468ca46ec7a148d0bd5173945bce06b689575430d7fda2f13e201042` |
| 53 | joins | /segment_cnv_occurrences | 979 | 1085 | `f38ed8b981f0d53aa68db9ca06b41c60fbad8bb4c31d9e951fe083e5624ae736` |
| 54 | joins | /analysis/survival | 90994 | 2769 | `a92b4d00a109177fe74bd5b29270f7ad8e12667d067a9a79093c61ef94f4b072` |
| 55 | joins | /cnv_occurrences | 496 | 2328 | `fc1f913ec343fdd8e922a5f5483b8ace00c14a5084bf068295c28d3218549a5f` |
| 56 | expression-expanded | /gene_expression/values | 177710 | 2733 | `e5b3c22865fa374acf619be2a2bd82bf36720dd09ef8660f98431a951dbf31a0` |
| 57 | expression-expanded | /gene_expression/values | 186276 | 2437 | `dfe1a7c43f56fb8eab87fdb4f4168445c258ffc3ca12c55098ab309ce8b6e5b6` |
| 58 | expression-expanded | /gene_expression/values | 176989 | 2462 | `96235c580252ad60cbc95f5aa960e2e0c9a4e39d1dbed75d4f1b0d94dfe9f937` |
| 59 | expression-expanded | /gene_expression/values | 190645 | 2620 | `134422004ce913e6d1ce7c7c097684861838608aeed1c76b2949715599692743` |
| 60 | expression-expanded | /gene_expression/values | 191412 | 2483 | `94ec1e0f1b434a7d62ba699107a444c961c0250744e5529eff9d866e20cfd91d` |
| 61 | expression-expanded | /gene_expression/values | 169690 | 2751 | `d1f5e09e6c2a58b7b6c189d98355c35297cf953ad0316c8171b08f38452153c4` |
| 62 | expression-expanded | /gene_expression/values | 189114 | 2700 | `10bb5cf286b17d65facd6522c7a0e225937f633d15277d5d57c48e30de41fa19` |
| 63 | expression-expanded | /gene_expression/values | 187996 | 2392 | `b0f762843b97acf4c40a227e50bc5a297bc415d751639f81273093d063d8e5cd` |
| 64 | expression-expanded | /gene_expression/values | 188607 | 2379 | `8a94ce7f3ae41d0c02ad5e6f15e8a1f89bd1dbcc6f81581000d4b0ff023372f5` |
| 65 | expression-expanded | /gene_expression/values | 177940 | 2434 | `736384f127f31b8cff334431e38e4d066ef6235f3bf603f32fa09a702ef88866` |
| 66 | expression-expanded | /gene_expression/values | 60028 | 1798 | `85be429fc3a287f3f9cee65df3fe24b2cbff20cbdddbacbd357f7f9272cb4d05` |
| 67 | final | /cnv_occurrences | 661 | 1304 | `4a4a4df60789b38646b380ed25d15f318090e77da18a9810d15c6e597368ebb5` |
| 68 | final | /files | 792 | 1107 | `5785b6d5fefb5d873cefffa0c59a01cac30e3ccb9b8a64e791a2245405a2a575` |
| 69 | final | /cases | 1680 | 1153 | `586445e8dbd8edf517e613b67dbcbcd1964ad6893bd441cfadcf585efe0045f0` |
