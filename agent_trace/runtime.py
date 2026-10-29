"""Bind the tool descriptions and schemas in a prompt to their implementations."""

import json
import re
from threading import Lock

from agent_trace.agent.registry import ToolRegistry
from agent_trace.pipelines.bm25 import build
from agent_trace.pipelines.doc_retrieval import build_doc_index, search_docs as doc_search, read_doc as doc_read
from agent_trace.pipelines.email_retrieval import EmailBM25Retriever
from agent_trace.pipelines.email_qa import answer_email_question
from agent_trace.pipelines.daily_digest import generate_digest
from agent_trace.types import ToolSpec


def catalogue_from_system(system):
    matches = re.finditer(r'^Tool: (.+)\nDescription: (.*)\nParameters JSON Schema: (.+)$', system, re.MULTILINE)
    schemas = [{'name': m[1], 'description': m[2], 'parameters': json.loads(m[3])} for m in matches]
    if not schemas:
        raise ValueError('System prompt must contain Tool / Description / Parameters JSON Schema entries')
    names = [s['name'] for s in schemas]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate tool names in prompt')
    return schemas


def build_registry(aux_lm, corpus, system):
    index = None
    emails = None
    by_id = {}
    doc_lock = Lock()
    email_lock = Lock()

    def documents():
        nonlocal index
        with doc_lock:
            if index is None:
                index = build_doc_index(corpus.docs())
        return index

    def email_search():
        nonlocal emails, by_id
        with email_lock:
            if emails is None:
                records = corpus.emails()
                emails = EmailBM25Retriever(build([e['subject'] + '\n' + e['body'] for e in records]), records, verbose=False)
                by_id = {e['id']: e for e in records}
        return emails

    def search_docs(query, k=5):
        return json.dumps(doc_search(documents(), query, k), ensure_ascii=False)

    def read_doc(doc_id, start_line=1):
        return json.dumps(doc_read(documents(), doc_id, start_line), ensure_ascii=False)

    def search_emails(query, k=5):
        return json.dumps([{'id': e['id'], 'subject': e['subject'], 'date': e['date'], 'preview': e['body'][:600]}
                           for e in email_search()(query, k)], ensure_ascii=False)

    def read_email(email_id):
        email_search()
        return json.dumps(by_id[email_id], ensure_ascii=False)

    def email_qa(question):
        return json.dumps(answer_email_question(question, email_search(), aux_lm, max_hops=3, verbose=False), ensure_ascii=False)

    implemented = {'search_docs': search_docs, 'read_doc': read_doc, 'search_emails': search_emails,
                   'read_email': read_email, 'email_qa': email_qa,
                   'daily_digest': lambda date: generate_digest(corpus.emails_on(date), aux_lm)}

    def unavailable(name):
        def tool(**kwargs):
            raise NotImplementedError(f'{name} is not implemented in this research runtime')
        return tool

    return ToolRegistry([ToolSpec(s['name'], s['description'], s['parameters'],
                                  implemented.get(s['name'], unavailable(s['name'])),
                                  read_only=s['name'] != 'run_terminal')
                         for s in catalogue_from_system(system)])
