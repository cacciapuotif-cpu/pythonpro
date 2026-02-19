--
-- PostgreSQL database dump
--

\restrict coNQ7UZ8xepoUx13KzyQZPT9iC0MXVdEu06tcCkICwTfkhLuqkHblXWccugpByH

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO admin;

--
-- Name: assignments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.assignments (
    id integer NOT NULL,
    collaborator_id integer NOT NULL,
    project_id integer NOT NULL,
    role character varying(50) NOT NULL,
    assigned_hours double precision NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    hourly_rate double precision NOT NULL,
    contract_type character varying(50),
    completed_hours double precision,
    progress_percentage double precision,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.assignments OWNER TO admin;

--
-- Name: assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.assignments_id_seq OWNER TO admin;

--
-- Name: assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.assignments_id_seq OWNED BY public.assignments.id;


--
-- Name: attendances; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.attendances (
    id integer NOT NULL,
    collaborator_id integer NOT NULL,
    project_id integer NOT NULL,
    assignment_id integer,
    date timestamp without time zone NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    hours double precision NOT NULL,
    notes text,
    overtime_hours double precision,
    break_time_minutes integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.attendances OWNER TO admin;

--
-- Name: attendances_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.attendances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.attendances_id_seq OWNER TO admin;

--
-- Name: attendances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.attendances_id_seq OWNED BY public.attendances.id;


--
-- Name: collaborator_project; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.collaborator_project (
    collaborator_id integer NOT NULL,
    project_id integer NOT NULL
);


ALTER TABLE public.collaborator_project OWNER TO admin;

--
-- Name: collaborators; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.collaborators (
    id integer NOT NULL,
    first_name character varying(50) NOT NULL,
    last_name character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    phone character varying(20),
    "position" character varying(100),
    birthplace character varying(100),
    birth_date timestamp without time zone,
    gender character varying(10),
    fiscal_code character varying(16) NOT NULL,
    city character varying(100),
    address character varying(200),
    education character varying(50),
    is_active boolean,
    last_login timestamp without time zone,
    documento_identita_filename character varying(255),
    documento_identita_path character varying(500),
    documento_identita_uploaded_at timestamp without time zone,
    curriculum_filename character varying(255),
    curriculum_path character varying(500),
    curriculum_uploaded_at timestamp without time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.collaborators OWNER TO admin;

--
-- Name: collaborators_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.collaborators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.collaborators_id_seq OWNER TO admin;

--
-- Name: collaborators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.collaborators_id_seq OWNED BY public.collaborators.id;


--
-- Name: contract_templates; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.contract_templates (
    id integer NOT NULL,
    nome_template character varying(200) NOT NULL,
    descrizione text,
    tipo_contratto character varying(50) NOT NULL,
    contenuto_html text NOT NULL,
    intestazione text,
    pie_pagina text,
    include_logo_ente boolean,
    posizione_logo character varying(20),
    dimensione_logo character varying(20),
    include_clausola_privacy boolean,
    include_clausola_riservatezza boolean,
    include_clausola_proprieta_intellettuale boolean,
    formato_data character varying(20),
    formato_importo character varying(20),
    is_default boolean,
    is_active boolean,
    versione character varying(20),
    note_interne text,
    numero_utilizzi integer,
    ultimo_utilizzo timestamp without time zone,
    created_by character varying(100),
    updated_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.contract_templates OWNER TO admin;

--
-- Name: contract_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.contract_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.contract_templates_id_seq OWNER TO admin;

--
-- Name: contract_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.contract_templates_id_seq OWNED BY public.contract_templates.id;


--
-- Name: implementing_entities; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.implementing_entities (
    id integer NOT NULL,
    ragione_sociale character varying(200) NOT NULL,
    forma_giuridica character varying(50),
    partita_iva character varying(11) NOT NULL,
    codice_fiscale character varying(16),
    codice_ateco character varying(10),
    rea_numero character varying(20),
    registro_imprese character varying(100),
    indirizzo character varying(200),
    cap character varying(5),
    citta character varying(100),
    provincia character varying(2),
    nazione character varying(2),
    pec character varying(100),
    email character varying(100),
    telefono character varying(20),
    sdi character varying(7),
    iban character varying(27),
    intestatario_conto character varying(200),
    referente_nome character varying(50),
    referente_cognome character varying(50),
    referente_email character varying(100),
    referente_telefono character varying(20),
    referente_ruolo character varying(100),
    logo_filename character varying(255),
    logo_path character varying(500),
    logo_uploaded_at timestamp without time zone,
    note text,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.implementing_entities OWNER TO admin;

--
-- Name: implementing_entities_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.implementing_entities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.implementing_entities_id_seq OWNER TO admin;

--
-- Name: implementing_entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.implementing_entities_id_seq OWNED BY public.implementing_entities.id;


--
-- Name: login_attempts; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.login_attempts (
    id integer NOT NULL,
    username character varying(50),
    ip_address character varying(45),
    user_agent text,
    success boolean,
    failure_reason character varying(100),
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE public.login_attempts OWNER TO admin;

--
-- Name: login_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.login_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.login_attempts_id_seq OWNER TO admin;

--
-- Name: login_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.login_attempts_id_seq OWNED BY public.login_attempts.id;


--
-- Name: progetto_mansione_ente; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.progetto_mansione_ente (
    id integer NOT NULL,
    progetto_id integer NOT NULL,
    ente_attuatore_id integer NOT NULL,
    mansione character varying(100) NOT NULL,
    descrizione_mansione text,
    data_inizio timestamp without time zone NOT NULL,
    data_fine timestamp without time zone NOT NULL,
    ore_previste double precision NOT NULL,
    ore_effettive double precision,
    tariffa_oraria double precision,
    budget_totale double precision,
    tipo_contratto character varying(50),
    is_active boolean,
    note text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.progetto_mansione_ente OWNER TO admin;

--
-- Name: progetto_mansione_ente_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.progetto_mansione_ente_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.progetto_mansione_ente_id_seq OWNER TO admin;

--
-- Name: progetto_mansione_ente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.progetto_mansione_ente_id_seq OWNED BY public.progetto_mansione_ente.id;


--
-- Name: projects; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    status character varying(20),
    cup character varying(15),
    ente_erogatore character varying(50),
    ente_attuatore_id integer,
    priority integer,
    budget double precision,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.projects OWNER TO admin;

--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.projects_id_seq OWNER TO admin;

--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    hashed_password character varying(100) NOT NULL,
    full_name character varying(100),
    role character varying(20),
    is_active boolean,
    is_verified boolean,
    last_login timestamp without time zone,
    failed_login_attempts integer,
    locked_until timestamp without time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    collaborator_id integer
);


ALTER TABLE public.users OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: assignments id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.assignments ALTER COLUMN id SET DEFAULT nextval('public.assignments_id_seq'::regclass);


--
-- Name: attendances id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.attendances ALTER COLUMN id SET DEFAULT nextval('public.attendances_id_seq'::regclass);


--
-- Name: collaborators id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.collaborators ALTER COLUMN id SET DEFAULT nextval('public.collaborators_id_seq'::regclass);


--
-- Name: contract_templates id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contract_templates ALTER COLUMN id SET DEFAULT nextval('public.contract_templates_id_seq'::regclass);


--
-- Name: implementing_entities id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.implementing_entities ALTER COLUMN id SET DEFAULT nextval('public.implementing_entities_id_seq'::regclass);


--
-- Name: login_attempts id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.login_attempts ALTER COLUMN id SET DEFAULT nextval('public.login_attempts_id_seq'::regclass);


--
-- Name: progetto_mansione_ente id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.progetto_mansione_ente ALTER COLUMN id SET DEFAULT nextval('public.progetto_mansione_ente_id_seq'::regclass);


--
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.alembic_version (version_num) FROM stdin;
\.


--
-- Data for Name: assignments; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.assignments (id, collaborator_id, project_id, role, assigned_hours, start_date, end_date, hourly_rate, contract_type, completed_hours, progress_percentage, is_active, created_at, updated_at) FROM stdin;
1	1	1	docente	110	2025-10-20 00:00:00	2025-11-30 00:00:00	49.98	professionale	0	0	t	2025-10-25 15:55:30.947612+00	\N
2	1	1	docente	90	2025-10-20 00:00:00	2025-11-30 00:00:00	49.99	professionale	0	0	t	2025-10-25 15:58:07.780615+00	\N
3	1	1	docente	44	2025-10-24 00:00:00	2025-11-16 00:00:00	43.99	professionale	16	36.36363636363637	t	2025-10-26 11:23:52.427461+00	2025-10-26 17:13:25.185215+00
4	1	1	docente	33	2025-10-27 00:00:00	2025-11-30 00:00:00	33	professionale	0	0	t	2025-10-29 08:22:52.878246+00	\N
5	1	1	docente	44	2025-10-27 00:00:00	2025-11-09 00:00:00	49.99	professionale	0	0	t	2025-10-29 14:07:05.381152+00	\N
6	1	1	docente	44	2025-10-29 00:00:00	2025-11-09 00:00:00	43.99	professionale	0	0	t	2025-10-29 14:07:59.055519+00	\N
7	1	1	docente	11	2025-10-31 00:00:00	2025-11-09 00:00:00	10.98	professionale	0	0	t	2025-10-31 19:33:33.818286+00	\N
8	1	1	docente	11	2025-10-31 00:00:00	2025-11-07 00:00:00	10.98	professionale	0	0	t	2025-10-31 19:39:23.438368+00	\N
9	2	1	docente	11	2025-10-31 00:00:00	2025-11-05 00:00:00	10.99	professionale	0	0	t	2025-10-31 19:39:54.255393+00	\N
10	1	1	docente	44	2025-10-31 00:00:00	2025-11-09 00:00:00	43.99	professionale	0	0	t	2025-10-31 19:40:59.781655+00	\N
11	1	1	docente	22	2025-10-31 00:00:00	2025-11-09 00:00:00	21.98	professionale	0	0	t	2025-10-31 19:42:12.537441+00	\N
12	1	1	docente	22	2025-10-31 00:00:00	2025-11-09 00:00:00	21.98	professionale	0	0	t	2025-10-31 19:45:10.778046+00	\N
\.


--
-- Data for Name: attendances; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.attendances (id, collaborator_id, project_id, assignment_id, date, start_time, end_time, hours, notes, overtime_hours, break_time_minutes, created_at, updated_at) FROM stdin;
1	1	1	3	2025-10-07 00:00:00	2025-10-07 09:00:00	2025-10-07 17:00:00	8		0	0	2025-10-26 17:13:12.976913+00	\N
2	1	1	3	2025-10-09 00:00:00	2025-10-09 09:00:00	2025-10-09 17:00:00	8		0	0	2025-10-26 17:13:25.164562+00	\N
\.


--
-- Data for Name: collaborator_project; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.collaborator_project (collaborator_id, project_id) FROM stdin;
1	1
2	1
\.


--
-- Data for Name: collaborators; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.collaborators (id, first_name, last_name, email, phone, "position", birthplace, birth_date, gender, fiscal_code, city, address, education, is_active, last_login, documento_identita_filename, documento_identita_path, documento_identita_uploaded_at, curriculum_filename, curriculum_path, curriculum_uploaded_at, created_at, updated_at) FROM stdin;
1	Francesco	Cacciapuoti	cacciapuotif@gmail.com	3939787431	Docente Senior	napoli	1974-01-29 00:00:00	maschio	CCCFNC74A29F889C	Napoli	via sant'Aspreno 13	master	t	\N	\N	\N	\N	\N	\N	\N	2025-10-25 15:49:12.262164+00	\N
2	Mario	Rossi	mario.rossi@example.com	3331234567	Sviluppatore	Roma	1980-01-01 00:00:00	maschio	RSSMRA80A01H501U	Roma	Via Roma 1	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-10-31 19:32:33.918858+00	\N
3	GIULIANA	CICCARELLI	gciccarelli8@gmail.com	3397608981	Sviluppatore	Mugnano di Napoli	1988-10-10 00:00:00	femmina	CCCGLN88R50F799Y	Giugliano in campania	Via A. Mario Pirozzi, 70	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
4	FELICE	RUSSILLO	felice.russillo@gmail.com	3933341420	Sviluppatore	Baragiano	1964-09-23 00:00:00	maschio	RSSFLC64P23A615F	Napoli	Via Domenico Forges Davanzati, 24	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
5	GIANPIERO	FALCO	gianpiero.falco@yahoo.it	3913945665	Sviluppatore	Napoli	1965-01-16 00:00:00	maschio	FLCGPR65A16F839K	Napoli	Viale privato Comola Ricci, 165	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
6	VALERIA	FINAMORE	valeria.finamore@gmail.com	3394427268	Sviluppatore	Napoli	1969-05-26 00:00:00	femmina	FNMVLR69E66F839G	Vico Equense	Via della cresta, 31	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
7	ROCCHINA	ROMANO	rocchina.romano@unibas.it	3939716654	Sviluppatore	Potenza	1974-01-12 00:00:00	femmina	RMNRCH74A52G942H	Potenza	Via Matera, 28	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
8	CLAUDIO	DE PIETRO	claudio.depietro110@gmail.com	3481423427	Sviluppatore	Napoli	1993-11-03 00:00:00	maschio	DPTCLD93S03F839G	Napoli	Largo Mimose, 5 int4 p.2	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
9	VALERIO	IACONO	valerio@ischia.it	3318859789	Sviluppatore	Napoli	1976-02-12 00:00:00	maschio	CNIVLR76B12F839A	Forio	Via Zappino, 14	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
10	FRANCESCA	IACONO	francescaiacono67@gmail.com	3483837591	Sviluppatore	Forio	1967-01-23 00:00:00	femmina	CNIFNC67A63D702V	Forio	Via Cognole, 15	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
11	FABRIZIO	CHERUBINI	fabrivento@inwind.it	3921559542	Sviluppatore	Napoli	2025-08-25 00:00:00	maschio	CHRFRZ63M25F839B	Napoli	Via Giambattista Licata, 6	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
12	VALENTINO	LIGOBBI	v.ligobbi@gmail.com	3386610790	Sviluppatore	Napoli	1973-12-21 00:00:00	maschio	LGBVNT73T21F839Y	Villaricca	Via della libertà, 494	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
13	GAETANO	ANDREOZZI	gaetano@hsmitalia.it	3397468296	Sviluppatore	Villaricca	1989-05-02 00:00:00	maschio	NDRGTN89E02G309K	Aversa	Via San felice, 22	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
14	VINCENZO	POLLINI	vincenzopollini@gmail.com	3334288336	Sviluppatore	Aversa	1985-02-20 00:00:00	maschio	PLLVCN85B20A512Z	Aversa	Via Presidio, 16	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
15	DOMENICO	CILENTO	domenicocilento1@gmail.com	3394143517	Sviluppatore	Napoli	1972-04-21 00:00:00	maschio	CLNDNC72D21F839H	Giugliano in campania	Via San giovanni a campo, 28	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
16	GIUSEPPINA	PEZZELLA	giusypezzella2013@gmail.com	3383573908	Sviluppatore	Napoli	1989-01-16 00:00:00	femmina	PZZGPP89A56F839Q	Grumo Nevano	Viale Eduardo Chiacchio, 5	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
17	ROSARIA	MARRONE	marrone.nextgroup@gmail.com	3275587085	Sviluppatore	Napoli	1983-05-02 00:00:00	femmina	MRRRSR83E42F839V	Aversa	Via Pelliccia, 11	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
18	ANTONELLA	GIGLIO	wondernellagiglio72@gmail.com	3467989514	Sviluppatore	Napoli	1972-07-27 00:00:00	femmina	GGLNNL72L67F839H	Portici	Piazza Sebastiano Poili, 1	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
19	SALVATORE	SCHIANO	schiano.salvatore74@gmail.com	3389105377	Sviluppatore	Napoli	1974-10-25 00:00:00	maschio	SCHSVT74R25F839O	Napoli	Via Fratelli cervi 108 Isol. D	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
20	GIUSEPPE	SORRENTINO	giuseppesorrentino10@gmail.com	3314161716	Sviluppatore	Torre del greco	1981-04-13 00:00:00	maschio	SRRGPP81D13L259I	Torre del greco	Viale Castelluccio, 25	diploma	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
21	EMANUELE	SCUOTTO	e.scuotto@eidongroup.it	3299222351	Sviluppatore	Napoli	1981-03-26 00:00:00	maschio	SCTMNL81C26F839F	Napoli	Corso Vittorio Emanuele, 544	laurea	t	\N	\N	\N	\N	\N	\N	\N	2025-11-05 10:02:31.742139+00	\N
\.


--
-- Data for Name: contract_templates; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.contract_templates (id, nome_template, descrizione, tipo_contratto, contenuto_html, intestazione, pie_pagina, include_logo_ente, posizione_logo, dimensione_logo, include_clausola_privacy, include_clausola_riservatezza, include_clausola_proprieta_intellettuale, formato_data, formato_importo, is_default, is_active, versione, note_interne, numero_utilizzi, ultimo_utilizzo, created_by, updated_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: implementing_entities; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.implementing_entities (id, ragione_sociale, forma_giuridica, partita_iva, codice_fiscale, codice_ateco, rea_numero, registro_imprese, indirizzo, cap, citta, provincia, nazione, pec, email, telefono, sdi, iban, intestatario_conto, referente_nome, referente_cognome, referente_email, referente_telefono, referente_ruolo, logo_filename, logo_path, logo_uploaded_at, note, is_active, created_at, updated_at) FROM stdin;
1	Next Group srl	S.r.l.	00000000002	00000000002	70.22.09	MI-000002	Milano	VIA SANT'ASPRENO 13	80133	Napoli	NA	It	omniservizi@legalmail.it	cacciapuotif@gmail.com	3939787431	0000000	IT60X0542811101000000123456	next group srl	Francesco	Cacciapuoti	cacciapuotif@gmail.com	+393939787431	Amministratore	\N	\N	\N	\N	t	2025-10-25 15:52:02.575835+00	\N
\.


--
-- Data for Name: login_attempts; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.login_attempts (id, username, ip_address, user_agent, success, failure_reason, "timestamp") FROM stdin;
\.


--
-- Data for Name: progetto_mansione_ente; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.progetto_mansione_ente (id, progetto_id, ente_attuatore_id, mansione, descrizione_mansione, data_inizio, data_fine, ore_previste, ore_effettive, tariffa_oraria, budget_totale, tipo_contratto, is_active, note, created_at, updated_at) FROM stdin;
1	1	1	docente		2025-10-20 00:00:00	2025-11-30 23:59:59	100	0	49.97	\N	Professionale	t		2025-10-25 15:54:38.600281+00	\N
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.projects (id, name, description, start_date, end_date, status, cup, ente_erogatore, ente_attuatore_id, priority, budget, is_active, created_at, updated_at) FROM stdin;
1	Progetto Test	progetti test	2025-10-20 00:00:00	2025-11-30 23:59:59	active	c12c11223334884	FONDIMPRESA	\N	1	\N	t	2025-10-25 15:53:18.263584+00	2025-10-29 14:07:22.1828+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.users (id, username, email, hashed_password, full_name, role, is_active, is_verified, last_login, failed_login_attempts, locked_until, created_at, updated_at, collaborator_id) FROM stdin;
1	admin	admin@gestionale.local	$2b$12$IITtYUmZqAAtqRx2jBcbYebWbUJBv5hyhw1VslQcN9eBdbdVBprGa	Amministratore Sistema	admin	t	f	\N	0	\N	2025-10-24 09:52:00.889242+00	\N	\N
\.


--
-- Name: assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.assignments_id_seq', 44, true);


--
-- Name: attendances_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.attendances_id_seq', 2, true);


--
-- Name: collaborators_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.collaborators_id_seq', 21, true);


--
-- Name: contract_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.contract_templates_id_seq', 1, false);


--
-- Name: implementing_entities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.implementing_entities_id_seq', 1, true);


--
-- Name: login_attempts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.login_attempts_id_seq', 1, false);


--
-- Name: progetto_mansione_ente_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.progetto_mansione_ente_id_seq', 1, true);


--
-- Name: projects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.projects_id_seq', 1, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.users_id_seq', 1, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: assignments assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_pkey PRIMARY KEY (id);


--
-- Name: attendances attendances_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.attendances
    ADD CONSTRAINT attendances_pkey PRIMARY KEY (id);


--
-- Name: collaborator_project collaborator_project_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.collaborator_project
    ADD CONSTRAINT collaborator_project_pkey PRIMARY KEY (collaborator_id, project_id);


--
-- Name: collaborators collaborators_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.collaborators
    ADD CONSTRAINT collaborators_pkey PRIMARY KEY (id);


--
-- Name: contract_templates contract_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contract_templates
    ADD CONSTRAINT contract_templates_pkey PRIMARY KEY (id);


--
-- Name: implementing_entities implementing_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.implementing_entities
    ADD CONSTRAINT implementing_entities_pkey PRIMARY KEY (id);


--
-- Name: login_attempts login_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.login_attempts
    ADD CONSTRAINT login_attempts_pkey PRIMARY KEY (id);


--
-- Name: progetto_mansione_ente progetto_mansione_ente_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.progetto_mansione_ente
    ADD CONSTRAINT progetto_mansione_ente_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_active_assignments; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_active_assignments ON public.assignments USING btree (is_active, start_date);


--
-- Name: idx_citta_provincia; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_citta_provincia ON public.implementing_entities USING btree (citta, provincia);


--
-- Name: idx_collaborator_project_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_collaborator_project_role ON public.assignments USING btree (collaborator_id, project_id, role);


--
-- Name: idx_date_range; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_date_range ON public.assignments USING btree (start_date, end_date);


--
-- Name: idx_mansione_attiva; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_mansione_attiva ON public.progetto_mansione_ente USING btree (mansione, is_active);


--
-- Name: idx_periodo_mansione; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_periodo_mansione ON public.progetto_mansione_ente USING btree (data_inizio, data_fine);


--
-- Name: idx_progetto_ente; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_progetto_ente ON public.progetto_mansione_ente USING btree (progetto_id, ente_attuatore_id);


--
-- Name: idx_ragione_sociale_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ragione_sociale_active ON public.implementing_entities USING btree (ragione_sociale, is_active);


--
-- Name: idx_tipo_contratto_attivo; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tipo_contratto_attivo ON public.contract_templates USING btree (tipo_contratto, is_active);


--
-- Name: idx_tipo_default; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tipo_default ON public.contract_templates USING btree (tipo_contratto, is_default);


--
-- Name: idx_unique_default_per_tipo; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_unique_default_per_tipo ON public.contract_templates USING btree (tipo_contratto, is_default);


--
-- Name: idx_unique_progetto_ente_mansione; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_unique_progetto_ente_mansione ON public.progetto_mansione_ente USING btree (progetto_id, ente_attuatore_id, mansione, data_inizio);


--
-- Name: ix_assignments_collaborator_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_collaborator_id ON public.assignments USING btree (collaborator_id);


--
-- Name: ix_assignments_contract_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_contract_type ON public.assignments USING btree (contract_type);


--
-- Name: ix_assignments_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_created_at ON public.assignments USING btree (created_at);


--
-- Name: ix_assignments_end_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_end_date ON public.assignments USING btree (end_date);


--
-- Name: ix_assignments_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_id ON public.assignments USING btree (id);


--
-- Name: ix_assignments_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_is_active ON public.assignments USING btree (is_active);


--
-- Name: ix_assignments_project_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_project_id ON public.assignments USING btree (project_id);


--
-- Name: ix_assignments_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_role ON public.assignments USING btree (role);


--
-- Name: ix_assignments_start_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_assignments_start_date ON public.assignments USING btree (start_date);


--
-- Name: ix_attendances_assignment_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_assignment_id ON public.attendances USING btree (assignment_id);


--
-- Name: ix_attendances_collaborator_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_collaborator_id ON public.attendances USING btree (collaborator_id);


--
-- Name: ix_attendances_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_created_at ON public.attendances USING btree (created_at);


--
-- Name: ix_attendances_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_date ON public.attendances USING btree (date);


--
-- Name: ix_attendances_hours; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_hours ON public.attendances USING btree (hours);


--
-- Name: ix_attendances_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_id ON public.attendances USING btree (id);


--
-- Name: ix_attendances_project_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_attendances_project_id ON public.attendances USING btree (project_id);


--
-- Name: ix_collaborators_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_created_at ON public.collaborators USING btree (created_at);


--
-- Name: ix_collaborators_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_collaborators_email ON public.collaborators USING btree (email);


--
-- Name: ix_collaborators_first_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_first_name ON public.collaborators USING btree (first_name);


--
-- Name: ix_collaborators_fiscal_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_collaborators_fiscal_code ON public.collaborators USING btree (fiscal_code);


--
-- Name: ix_collaborators_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_id ON public.collaborators USING btree (id);


--
-- Name: ix_collaborators_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_is_active ON public.collaborators USING btree (is_active);


--
-- Name: ix_collaborators_last_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_last_name ON public.collaborators USING btree (last_name);


--
-- Name: ix_collaborators_position; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_collaborators_position ON public.collaborators USING btree ("position");


--
-- Name: ix_contract_templates_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_created_at ON public.contract_templates USING btree (created_at);


--
-- Name: ix_contract_templates_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_id ON public.contract_templates USING btree (id);


--
-- Name: ix_contract_templates_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_is_active ON public.contract_templates USING btree (is_active);


--
-- Name: ix_contract_templates_is_default; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_is_default ON public.contract_templates USING btree (is_default);


--
-- Name: ix_contract_templates_nome_template; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_nome_template ON public.contract_templates USING btree (nome_template);


--
-- Name: ix_contract_templates_tipo_contratto; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_contract_templates_tipo_contratto ON public.contract_templates USING btree (tipo_contratto);


--
-- Name: ix_implementing_entities_citta; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_citta ON public.implementing_entities USING btree (citta);


--
-- Name: ix_implementing_entities_codice_fiscale; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_codice_fiscale ON public.implementing_entities USING btree (codice_fiscale);


--
-- Name: ix_implementing_entities_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_created_at ON public.implementing_entities USING btree (created_at);


--
-- Name: ix_implementing_entities_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_id ON public.implementing_entities USING btree (id);


--
-- Name: ix_implementing_entities_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_is_active ON public.implementing_entities USING btree (is_active);


--
-- Name: ix_implementing_entities_partita_iva; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_implementing_entities_partita_iva ON public.implementing_entities USING btree (partita_iva);


--
-- Name: ix_implementing_entities_pec; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_pec ON public.implementing_entities USING btree (pec);


--
-- Name: ix_implementing_entities_ragione_sociale; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_implementing_entities_ragione_sociale ON public.implementing_entities USING btree (ragione_sociale);


--
-- Name: ix_login_attempts_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_login_attempts_id ON public.login_attempts USING btree (id);


--
-- Name: ix_login_attempts_success; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_login_attempts_success ON public.login_attempts USING btree (success);


--
-- Name: ix_login_attempts_timestamp; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_login_attempts_timestamp ON public.login_attempts USING btree ("timestamp");


--
-- Name: ix_login_attempts_username; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_login_attempts_username ON public.login_attempts USING btree (username);


--
-- Name: ix_progetto_mansione_ente_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_created_at ON public.progetto_mansione_ente USING btree (created_at);


--
-- Name: ix_progetto_mansione_ente_data_fine; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_data_fine ON public.progetto_mansione_ente USING btree (data_fine);


--
-- Name: ix_progetto_mansione_ente_data_inizio; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_data_inizio ON public.progetto_mansione_ente USING btree (data_inizio);


--
-- Name: ix_progetto_mansione_ente_ente_attuatore_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_ente_attuatore_id ON public.progetto_mansione_ente USING btree (ente_attuatore_id);


--
-- Name: ix_progetto_mansione_ente_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_id ON public.progetto_mansione_ente USING btree (id);


--
-- Name: ix_progetto_mansione_ente_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_is_active ON public.progetto_mansione_ente USING btree (is_active);


--
-- Name: ix_progetto_mansione_ente_mansione; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_mansione ON public.progetto_mansione_ente USING btree (mansione);


--
-- Name: ix_progetto_mansione_ente_progetto_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_progetto_id ON public.progetto_mansione_ente USING btree (progetto_id);


--
-- Name: ix_progetto_mansione_ente_tipo_contratto; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_progetto_mansione_ente_tipo_contratto ON public.progetto_mansione_ente USING btree (tipo_contratto);


--
-- Name: ix_projects_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_created_at ON public.projects USING btree (created_at);


--
-- Name: ix_projects_cup; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_cup ON public.projects USING btree (cup);


--
-- Name: ix_projects_end_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_end_date ON public.projects USING btree (end_date);


--
-- Name: ix_projects_ente_attuatore_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_ente_attuatore_id ON public.projects USING btree (ente_attuatore_id);


--
-- Name: ix_projects_ente_erogatore; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_ente_erogatore ON public.projects USING btree (ente_erogatore);


--
-- Name: ix_projects_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_id ON public.projects USING btree (id);


--
-- Name: ix_projects_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_is_active ON public.projects USING btree (is_active);


--
-- Name: ix_projects_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_name ON public.projects USING btree (name);


--
-- Name: ix_projects_priority; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_priority ON public.projects USING btree (priority);


--
-- Name: ix_projects_start_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_start_date ON public.projects USING btree (start_date);


--
-- Name: ix_projects_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_status ON public.projects USING btree (status);


--
-- Name: ix_users_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_users_created_at ON public.users USING btree (created_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_users_is_active ON public.users USING btree (is_active);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: assignments assignments_collaborator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES public.collaborators(id) ON DELETE CASCADE;


--
-- Name: assignments assignments_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: attendances attendances_assignment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.attendances
    ADD CONSTRAINT attendances_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES public.assignments(id) ON DELETE SET NULL;


--
-- Name: attendances attendances_collaborator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.attendances
    ADD CONSTRAINT attendances_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES public.collaborators(id) ON DELETE CASCADE;


--
-- Name: attendances attendances_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.attendances
    ADD CONSTRAINT attendances_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: collaborator_project collaborator_project_collaborator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.collaborator_project
    ADD CONSTRAINT collaborator_project_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES public.collaborators(id);


--
-- Name: collaborator_project collaborator_project_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.collaborator_project
    ADD CONSTRAINT collaborator_project_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: progetto_mansione_ente progetto_mansione_ente_ente_attuatore_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.progetto_mansione_ente
    ADD CONSTRAINT progetto_mansione_ente_ente_attuatore_id_fkey FOREIGN KEY (ente_attuatore_id) REFERENCES public.implementing_entities(id) ON DELETE CASCADE;


--
-- Name: progetto_mansione_ente progetto_mansione_ente_progetto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.progetto_mansione_ente
    ADD CONSTRAINT progetto_mansione_ente_progetto_id_fkey FOREIGN KEY (progetto_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: projects projects_ente_attuatore_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_ente_attuatore_id_fkey FOREIGN KEY (ente_attuatore_id) REFERENCES public.implementing_entities(id);


--
-- Name: users users_collaborator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES public.collaborators(id);


--
-- PostgreSQL database dump complete
--

\unrestrict coNQ7UZ8xepoUx13KzyQZPT9iC0MXVdEu06tcCkICwTfkhLuqkHblXWccugpByH

