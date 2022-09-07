BEGIN;

-- GLOSSARY

-- additional publication frequencies
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (137, 'dataset.publication_frequency', 'QUA', 'Quarterly', 'Update data every three months', 4, NULL, NULL, NULL, NULL, NULL, NULL, 'Vierteljährlich', 'Daten werden vierteljährlich aktualisiert') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (138, 'dataset.publication_frequency', 'FTN', 'Fortnightly', 'Update data every two weeks', 6, NULL, NULL, NULL, NULL, NULL, NULL, 'Zweiwöchentlich', 'Daten werden vierzehntägig aktualisiert') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (139, 'dataset.publication_frequency', 'CON', 'Continual', 'Data is repeatedly and frequently updated', 9, NULL, NULL, NULL, NULL, NULL, NULL, 'Kontinuierlich', 'Daten werden ständig aktualisiert') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (140, 'dataset.publication_frequency', 'UNK', 'Unknown', 'Frequency of maintenance for the data is not known', 12, NULL, NULL, NULL, NULL, NULL, NULL, 'Unbekannt', 'Ein Aktualisierungsintervall ist nicht bekannt') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('dataset.publication_frequency', 'Y05', 'Every 5 years', 'Update data every five years', 25, NULL, NULL, NULL, NULL, NULL, NULL, 'Alle 5 Jahre', 'Daten werden alle fünf Jahre aktualisiert') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('dataset.publication_frequency', 'Y06', 'Every 6 years', 'Update data every six years', 26, NULL, NULL, NULL, NULL, NULL, NULL, 'Alle 6 Jahre', 'Daten werden alle sechs Jahre aktualisiert') ON CONFLICT DO NOTHING;

-- additional link types
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('link.type', 'directory', 'a directory', 'Directory on the local filesystem', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ein Ordner', 'Ein Ordner auf dem lokalen Dateisystem') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en) VALUES ('link.mime', 'directory', 'inode/directory', 'directory (not an official MIME type') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('link.type', 'ESRI:SHP', 'ESRI Shapefile', 'Vector layer in Shapefile format (.shp)', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ESRI Shapefile', 'Vektorlayer im Shapefile-Format (.shp)') ON CONFLICT DO NOTHING;

-- additional contact roles
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('contact.contact_role', 'WA', 'WMS/WFS Administrator', 'Person or party who can aid with WMS/WFS issues', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'WMS/WFS-Ansprechpartner', 'Person oder Stelle, die bei WMS/WFS-Problemen weiterhelfen kann') ON CONFLICT DO NOTHING;
INSERT INTO pgmetadata.glossary (field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES ('contact.contact_role', 'GA', 'GIS Administrator', 'Person or party who can aid with GIS-related issues', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'WMS/WFS-Ansprechpartner', 'Person oder Stelle, die in allen GIS technischen Angelegenheiten weiterhelfen kann') ON CONFLICT DO NOTHING;

SELECT pg_catalog.setval('pgmetadata.glossary_id_seq', 147, true);


-- new item_order for existing publication frequencies

CREATE TABLE pgmetadata.t_glossary (field text, code text, item_order smallint);
INSERT INTO pgmetadata.t_glossary (field, code, item_order)
VALUES
('dataset.publication_frequency', 'MON', 5),
('dataset.publication_frequency', 'WEE', 7),
('dataset.publication_frequency', 'DAY', 8),
('dataset.publication_frequency', 'IRR', 10),
('dataset.publication_frequency', 'NOP', 11)
ON CONFLICT DO NOTHING;

UPDATE pgmetadata.glossary AS g
SET item_order = t.item_order
FROM pgmetadata.t_glossary AS t
WHERE g.field = t.field AND g.code = t.code;

DROP TABLE pgmetadata.t_glossary;


-- DATASET

-- Add license_attribution and project_number fields to table dataset

ALTER TABLE pgmetadata.dataset ADD COLUMN IF NOT EXISTS license_attribution text;
ALTER TABLE pgmetadata.dataset ADD COLUMN IF NOT EXISTS project_number text;
COMMENT ON COLUMN pgmetadata.dataset.license_attribution IS 'License attribution / copyright notice';
COMMENT ON COLUMN pgmetadata.dataset.project_number IS 'Project number(s)';


-- Add license_attribution and project number to view v_dataset
-- Change scale number separator to colon (e.g. 1:1000)

CREATE OR REPLACE VIEW pgmetadata.v_dataset AS
 WITH glossary AS (
         SELECT COALESCE(current_setting('pgmetadata.locale'::text, true), 'en'::text) AS locale,
            v_glossary.dict
           FROM pgmetadata.v_glossary
        ), s AS (
         SELECT d.id,
            d.uid,
            d.table_name,
            d.schema_name,
            d.title,
            d.abstract,
            d.categories,
            d.themes,
            d.keywords,
            d.spatial_level,
            d.minimum_optimal_scale,
            d.maximum_optimal_scale,
            d.publication_date,
            d.publication_frequency,
            d.license,
            d.license_attribution,
            d.project_number,
            d.confidentiality,
            d.feature_count,
            d.geometry_type,
            d.projection_name,
            d.projection_authid,
            d.spatial_extent,
            d.creation_date,
            d.update_date,
            d.data_last_update,
            d.geom,
            cat.cat,
            theme.theme
           FROM ((pgmetadata.dataset d
             LEFT JOIN LATERAL unnest(d.categories) cat(cat) ON (true))
             LEFT JOIN LATERAL unnest(d.themes) theme(theme) ON (true))
          WHERE true
          ORDER BY d.id
        ), ss AS (
         SELECT s.id,
            s.uid,
            s.table_name,
            s.schema_name,
            s.title,
            s.abstract,
            ((((glossary.dict -> 'dataset.categories'::text) -> s.cat) -> 'label'::text) ->> glossary.locale) AS cat,
            gtheme.label AS theme,
            s.keywords,
            s.spatial_level,
            ('1 : '::text || s.minimum_optimal_scale) AS minimum_optimal_scale,
            ('1 : '::text || s.maximum_optimal_scale) AS maximum_optimal_scale,
            s.publication_date,
            ((((glossary.dict -> 'dataset.publication_frequency'::text) -> s.publication_frequency) -> 'label'::text) ->> glossary.locale) AS publication_frequency,
            ((((glossary.dict -> 'dataset.license'::text) -> s.license) -> 'label'::text) ->> glossary.locale) AS license,
            s.license_attribution,
            s.project_number,
            ((((glossary.dict -> 'dataset.confidentiality'::text) -> s.confidentiality) -> 'label'::text) ->> glossary.locale) AS confidentiality,
            s.feature_count,
            s.geometry_type,
            (regexp_split_to_array((rs.srtext)::text, '"'::text))[2] AS projection_name,
            s.projection_authid,
            s.spatial_extent,
            s.creation_date,
            s.update_date,
            s.data_last_update
           FROM glossary,
            ((s
             LEFT JOIN pgmetadata.theme gtheme ON ((gtheme.code = s.theme)))
             LEFT JOIN public.spatial_ref_sys rs ON ((concat(rs.auth_name, ':', rs.auth_srid) = s.projection_authid)))
        )
 SELECT ss.id,
    ss.uid,
    ss.table_name,
    ss.schema_name,
    ss.title,
    ss.abstract,
    string_agg(DISTINCT ss.cat, ', '::text ORDER BY ss.cat) AS categories,
    string_agg(DISTINCT ss.theme, ', '::text ORDER BY ss.theme) AS themes,
    ss.keywords,
    ss.spatial_level,
    ss.minimum_optimal_scale,
    ss.maximum_optimal_scale,
    ss.publication_date,
    ss.publication_frequency,
    ss.license,
    ss.confidentiality,
    ss.feature_count,
    ss.geometry_type,
    ss.projection_name,
    ss.projection_authid,
    ss.spatial_extent,
    ss.creation_date,
    ss.update_date,
    ss.data_last_update,
    ss.license_attribution,
    ss.project_number
   FROM ss
  GROUP BY ss.id, ss.uid, ss.table_name, ss.schema_name, ss.title, ss.abstract, ss.keywords, ss.spatial_level, ss.minimum_optimal_scale, ss.maximum_optimal_scale, ss.publication_date, ss.publication_frequency, ss.license, ss.license_attribution, ss.project_number, ss.confidentiality, ss.feature_count, ss.geometry_type, ss.projection_name, ss.projection_authid, ss.spatial_extent, ss.creation_date, ss.update_date, ss.data_last_update;


-- VIEW v_dataset
COMMENT ON VIEW pgmetadata.v_dataset IS 'Formatted version of dataset data, with all the codes replaced by corresponding labels taken from pgmetadata.glossary. Used in the function in charge of building the HTML metadata content.';


COMMIT;
