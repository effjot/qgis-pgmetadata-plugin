BEGIN;

-- GLOSSARY

-- additional publication frequencies

INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (137, 'dataset.publication_frequency', 'QUA', 'Quarterly', 'Update data every three months', 4, NULL, NULL, NULL, NULL, NULL, NULL, 'vierteljährlich', 'Daten werden vierteljährlich aktualisiert');
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (138, 'dataset.publication_frequency', 'FTN', 'Fortnightly', 'Update data every two weeks', 6, NULL, NULL, NULL, NULL, NULL, NULL, 'zweiwöchentlich', 'Daten werden vierzehntägig aktualisiert');
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (139, 'dataset.publication_frequency', 'CON', 'Continual', 'Data is repeatedly and frequently updated', 9, NULL, NULL, NULL, NULL, NULL, NULL, 'kontinuierlich', 'Daten werden ständig aktualisiert');
INSERT INTO pgmetadata.glossary (id, field, code, label_en, description_en, item_order, label_fr, description_fr, label_it, description_it, label_es, description_es, label_de, description_de) VALUES (140, 'dataset.publication_frequency', 'UNK', 'Unknown', 'Frequency of maintenance for the data is not known', 12, NULL, NULL, NULL, NULL, NULL, NULL, 'unbekannt', 'ein Aktualisierungsintervall ist nicht bekannt');

SELECT pg_catalog.setval('pgmetadata.glossary_id_seq', 140, true);


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

-- new field license_attribution

ALTER TABLE pgmetadata.dataset ADD COLUMN IF NOT EXISTS license_attribution text;

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
            ('1/'::text || s.minimum_optimal_scale) AS minimum_optimal_scale,
            ('1/'::text || s.maximum_optimal_scale) AS maximum_optimal_scale,
            s.publication_date,
            ((((glossary.dict -> 'dataset.publication_frequency'::text) -> s.publication_frequency) -> 'label'::text) ->> glossary.locale) AS publication_frequency,
            ((((glossary.dict -> 'dataset.license'::text) -> s.license) -> 'label'::text) ->> glossary.locale) AS license,
            s.license_attribution,
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
    ss.license_attribution
   FROM ss
  GROUP BY ss.id, ss.uid, ss.table_name, ss.schema_name, ss.title, ss.abstract, ss.keywords, ss.spatial_level, ss.minimum_optimal_scale, ss.maximum_optimal_scale, ss.publication_date, ss.publication_frequency, ss.license, ss.license_attribution, ss.confidentiality, ss.feature_count, ss.geometry_type, ss.projection_name, ss.projection_authid, ss.spatial_extent, ss.creation_date, ss.update_date, ss.data_last_update;



-- ADD RASTER SUPPORT

DROP FUNCTION pgmetadata.calculate_fields_from_data() CASCADE;
CREATE FUNCTION pgmetadata.calculate_fields_from_data() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    test_target_table regclass;
    target_table text;
    test_geom_column record;
    test_rast_column record;
    geom_envelop geometry;
    geom_column_name text;
    rast_column_name text;
BEGIN

    -- table
    target_table = quote_ident(NEW.schema_name) || '.' || quote_ident(NEW.table_name);
    IF target_table IS NULL THEN
        RETURN NEW;
    END IF;

    -- Check if table exists
    EXECUTE 'SELECT to_regclass(' || quote_literal(target_table) ||')'
    INTO test_target_table
    ;
    IF test_target_table IS NULL THEN
        RAISE NOTICE 'pgmetadata - table does not exists: %', target_table;
        RETURN NEW;
    END IF;

-- Get table feature count
    EXECUTE 'SELECT COUNT(*) FROM ' || target_table
    INTO NEW.feature_count;
    -- RAISE NOTICE 'pgmetadata - % feature_count: %', target_table, NEW.feature_count;

-- Check geometry properties: get data from geometry_columns and raster_columns
    EXECUTE
    ' SELECT *' ||
    ' FROM geometry_columns' ||
    ' WHERE f_table_schema=' || quote_literal(NEW.schema_name) ||
    ' AND f_table_name=' || quote_literal(NEW.table_name) ||
    ' LIMIT 1'
    INTO test_geom_column;

    EXECUTE
    ' SELECT *' ||
    ' FROM raster_columns' ||
    ' WHERE r_table_schema=' || quote_literal(NEW.schema_name) ||
    ' AND r_table_name=' || quote_literal(NEW.table_name) ||
    ' LIMIT 1'
    INTO test_rast_column;

-- If the table has a geometry column, calculate field values
    IF test_geom_column IS NOT NULL THEN

        -- column name
        geom_column_name = test_geom_column.f_geometry_column;
        RAISE NOTICE 'pgmetadata - table % has a geometry column: %', target_table, geom_column_name;

        -- spatial_extent
        EXECUTE '
            SELECT CONCAT(
                min(ST_xmin("' || geom_column_name || '"))::text, '', '',
                max(ST_xmax("' || geom_column_name || '"))::text, '', '',
                min(ST_ymin("' || geom_column_name || '"))::text, '', '',
                max(ST_ymax("' || geom_column_name || '"))::text)
            FROM ' || target_table
        INTO NEW.spatial_extent;

        -- geom: convexhull from target table
        EXECUTE '
            SELECT ST_Transform(ST_ConvexHull(st_collect(ST_Force2d("' || geom_column_name || '"))), 4326)
            FROM ' || target_table
        INTO geom_envelop;

        -- Test if it's not a point or a line
        IF GeometryType(geom_envelop) != 'POLYGON' THEN
            EXECUTE '
                SELECT ST_SetSRID(ST_Buffer(ST_GeomFromText(''' || ST_ASTEXT(geom_envelop) || '''), 0.0001), 4326)'
            INTO NEW.geom;
        ELSE
            NEW.GEOM = geom_envelop;
        END IF;

        -- projection_authid
        EXECUTE '
            SELECT CONCAT(s.auth_name, '':'', ST_SRID(m."' || geom_column_name || '")::text)
            FROM ' || target_table || ' m, spatial_ref_sys s
            WHERE s.auth_srid = ST_SRID(m."' || geom_column_name || '")
            LIMIT 1'
        INTO NEW.projection_authid;

        -- projection_name
        -- TODO

        -- geometry_type
        NEW.geometry_type = test_geom_column.type;

    ELSIF test_rast_column is not null THEN
    
        -- column name
        rast_column_name = test_rast_column.r_raster_column;
        RAISE NOTICE 'pgmetadata - table % has a raster column: %', target_table, rast_column_name;

        -- TODO: is this the best way to get the raster extent? Could we use ST_xmin etc. on test_rast_column.extent?
        EXECUTE '
            SELECT CONCAT(
                min(ST_xmin(extent))::text, '', '',
                max(ST_xmax(extent))::text, '', '',
                min(ST_ymin(extent))::text, '', '',
                max(ST_ymax(extent))::text)
            FROM raster_columns
            WHERE r_table_schema=' || quote_literal(NEW.schema_name) ||
              'AND r_table_name=' || quote_literal(NEW.table_name)
        INTO NEW.spatial_extent;
        
        -- convexhull from target table
        EXECUTE '
            SELECT ST_Transform(ST_ConvexHull("' || rast_column_name || '"), 4326)
            FROM ' || target_table
        INTO geom_envelop;

        -- Test if it's not a point or a line
        IF GeometryType(geom_envelop) != 'POLYGON' THEN
            EXECUTE '
                SELECT ST_SetSRID(ST_Buffer(ST_GeomFromText(''' || ST_ASTEXT(geom_envelop) || '''), 0.0001), 4326)'
            INTO NEW.geom;
        ELSE
            NEW.GEOM = geom_envelop;
        END IF;

        -- projection_authid
        EXECUTE '
            SELECT CONCAT(s.auth_name, '':'', ST_SRID(m."' || rast_column_name || '")::text)
            FROM ' || target_table || ' m, spatial_ref_sys s
            WHERE s.auth_srid = ST_SRID(m."' || rast_column_name || '")
            LIMIT 1'
        INTO NEW.projection_authid;

        -- geometry_type
        NEW.geometry_type = 'RASTER';
    
    ELSE
    -- No geometry column found: we need to erase values
            NEW.geom = NULL;
            NEW.projection_authid = NULL;
            NEW.geometry_type = NULL;
            NEW.spatial_extent = NULL;
    END IF;

    RETURN NEW;
END;
$$;

-- FUNCTION calculate_fields_from_data()
COMMENT ON FUNCTION pgmetadata.calculate_fields_from_data() IS 'Update some fields content when updating or inserting a line in pgmetadata.dataset table.';

-- restore trigger
CREATE TRIGGER trg_calculate_fields_from_data BEFORE INSERT OR UPDATE ON pgmetadata.dataset FOR EACH ROW EXECUTE PROCEDURE pgmetadata.calculate_fields_from_data();


COMMIT;