BEGIN;


-- Issue #115 (fix backslashes in regexp substition for HTML templates)

-- generate_html_from_json(json, text)
DROP FUNCTION IF EXISTS pgmetadata.generate_html_from_json(json, text);
CREATE OR REPLACE FUNCTION pgmetadata.generate_html_from_json(_json_data json, _template_section text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    item record;
    html text;
BEGIN

    -- Get HTML template from html_template table
    SELECT content
    FROM pgmetadata.html_template AS h
    WHERE True
    AND section = _template_section
    INTO html
    ;
    IF html IS NULL THEN
        RETURN NULL;
    END IF;

    -- Get dataset item
    -- We transpose dataset record into rows such as
    -- col    | val
    -- id     | 1
    -- uid    | dfd3b73c-3cd3-40b7-b92d-aa0f625c86fe
    -- ...
    -- title  | My title
    -- For each row, we search and replace the [% "col" %] by val
    FOR item IN
        SELECT (line.d).key AS col, Coalesce((line.d).value, '') AS val
        FROM (
            SELECT json_each_text(_json_data) d
        ) AS line
    LOOP
        -- replace QGIS style field [% "my_field" %] by field value
        html = regexp_replace(
            html,
            concat('\[% *"?', item.col, '"? *%\]'),
            replace(item.val, '\', '\\'), -- escape backslashes in substitution string (\1...\9 refer to subexpressions)
            'g'
        )
        ;

    END LOOP;

    RETURN html;

END;
$$;

-- FUNCTION generate_html_from_json(_json_data json, _template_section text)
COMMENT ON FUNCTION pgmetadata.generate_html_from_json(_json_data json, _template_section text) IS 'Generate HTML content for the given JSON representation of a record and a given section, based on the template stored in the pgmetadata.html_template table. Template section controlled values are "main", "contact" and "link". If the corresponding line is not found in the pgmetadata.html_template table, NULL is returned.';


-- get_dataset_item_html_content(text, text, text)
DROP FUNCTION IF EXISTS get_dataset_item_html_content(text, text, text);
CREATE OR REPLACE FUNCTION pgmetadata.get_dataset_item_html_content(_table_schema text, _table_name text, _locale text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    locale_exists boolean;
    item record;
    dataset_rec record;
    sql_text text;
    json_data json;
    html text;
    html_contact text;
    html_link text;
    html_main text;
BEGIN
    -- Check if dataset exists
    SELECT *
    FROM pgmetadata.dataset
    WHERE True
    AND schema_name = _table_schema
    AND table_name = _table_name
    LIMIT 1
    INTO dataset_rec
    ;

    IF dataset_rec.id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Check if the _locale parameter corresponds to the available locales
    _locale = lower(_locale);
    SELECT _locale IN (SELECT locale FROM pgmetadata.v_locales)
    INTO locale_exists
    ;
    IF NOT locale_exists THEN
        _locale = 'en';
    END IF;

    -- Set locale
    -- We must use EXECUTE in order to have _locale to be correctly interpreted
    sql_text = concat('SET SESSION "pgmetadata.locale" = ', quote_literal(_locale));
    EXECUTE sql_text;

    -- Contacts
    html_contact = '';
    FOR json_data IN
        WITH a AS (
            SELECT *
            FROM pgmetadata.v_contact
            WHERE True
            AND schema_name = _table_schema
            AND table_name = _table_name
        )
        SELECT row_to_json(a.*)
        FROM a
    LOOP
        html_contact = concat(
            html_contact, '
            ',
            pgmetadata.generate_html_from_json(json_data, 'contact')
        );
    END LOOP;
    -- RAISE NOTICE 'html_contact: %', html_contact;

    -- Links
    html_link = '';
    FOR json_data IN
        WITH a AS (
            SELECT *
            FROM pgmetadata.v_link
            WHERE True
            AND schema_name = _table_schema
            AND table_name = _table_name
        )
        SELECT row_to_json(a.*)
        FROM a
    LOOP
        html_link = concat(
            html_link, '
            ',
            pgmetadata.generate_html_from_json(json_data, 'link')
        );
    END LOOP;
    --RAISE NOTICE 'html_link: %', html_link;

    -- Main
    html_main = '';
    WITH a AS (
        SELECT *
        FROM pgmetadata.v_dataset
        WHERE True
        AND schema_name = _table_schema
        AND table_name = _table_name
    )
    SELECT row_to_json(a.*)
    FROM a
    INTO json_data
    ;
    html_main = pgmetadata.generate_html_from_json(json_data, 'main');
    -- RAISE NOTICE 'html_main: %', html_main;

    IF html_main IS NULL THEN
        RETURN NULL;
    END IF;

    html = html_main;

    -- add contacts: [% "meta_contacts" %]
    html = regexp_replace(
        html,
        concat('\[% *"?meta_contacts"? *%\]'),
        coalesce(replace(html_contact, '\', '\\'), ''), -- escape backslashes in substitution string (\1...\9 refer to subexpressions)
        'g'
    );

    -- add links [% "meta_links" %]
    html = regexp_replace(
        html,
        concat('\[% *"?meta_links"? *%\]'),
        coalesce(replace(html_link, '\', '\\'), ''), -- escape backslashes in substitution string (\1...\9 refer to subexpressions)
        'g'
    );

    RETURN html;

END;
$$;

COMMENT ON FUNCTION pgmetadata.get_dataset_item_html_content(_table_schema text, _table_name text, _locale text) IS 'Generate the metadata HTML content for the given table and given language or NULL if no templates are stored in the pgmetadata.html_template table.';


COMMIT;
