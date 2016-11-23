#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['schema']

from yaml import load
from os.path import dirname, join


data = '''
---
oneOf:
  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [init]}
      device: {type: string}

  - type: object
    additionalProperties: false
    required: [id, type, plan]
    properties:
      id: {type: string}
      type: {enum: [plan]}
      plan:
        type: array
        items:
          type: object
          additionalProperties: false
          required: [start, end, type, uri]
          properties:
            start: {type: number}
            end: {type: number}
            type: {enum: [image, video]}
            uri: {type: string, pattern: '://'}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [request]}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [powerOff]}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [powerOn]}

  - type: object
    additionalProperties: false
    required: [id, type, play]
    properties:
      id: {type: string}
      type: {enum: [play]}
      play:
        type: object
        additionalProperties: false
        required: [type, uri]
        properties:
          type: {enum: [image, video]}
          uri: {type: string, pattern: '://'}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [stop]}

  - type: object
    additionalProperties: false
    required: [id, type, resolution]
    properties:
      id: {type: string}
      type: {enum: [resolution]}
      resolution:
        type: object
        additionalProperties: false
        required: [type]
        properties:
          type: {enum: [full, right, both]}
          urlRight: {type: string, pattern: '://'}
          urlBottom: {type: string, pattern: '://'}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [url]}
      urlRight: {type: string, pattern: '://'}
      urlBottom: {type: string, pattern: '://'}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [ping]}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [pong]}

  - type: object
    additionalProperties: false
    required: [id, type]
    properties:
      id: {type: string}
      type: {enum: [ok]}

  - type: object
    additionalProperties: false
    required: [id, type, code]
    properties:
      id: {type: string}
      type: {enum: [error]}
      code: {type: integer}
      message: {type: string}
'''
schema = load(data)


# vim:set sw=4 ts=4 et:
