import asyncio
import json
from contextlib import suppress

from aiogram import types, exceptions
from aiogram.utils.markdown import hbold, hitalic, hide_link
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State

from botapp.utils import decode_deep_link, question_keyboard
from mainapp import models
from mainapp.models import Locale as L

from .bot import dp


class PollStates(StatesGroup):
    teacher_type = State()
    questions = State()
    open_question = State()


"""
data:
    teacher_n_group = teacher
    teacher_type = ...
    q2a = dict(
        question_id: None
        question_id: user answer
    )
    open_q = user answ
"""


@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    try:
        teacher_id, group_id = decode_deep_link(message.get_args())
        teacher_n_group = models.TeacherNGroup.objects.get(teacher_id=teacher_id, group_id=group_id)
    except (ValueError, models.TeacherNGroup.DoesNotExist):
        return await message.answer(L['wrong teacher'])

    if models.Result.objects.filter(user_id=message.from_user.id, teacher_n_group=teacher_n_group).count():
        await message.answer(L['same_teacher_again'])

    await state.update_data(teacher_n_group=teacher_n_group)

    teacher = teacher_n_group.teacher
    await message.answer(hide_link(teacher.photo) + L['teacher_text'].format(teacher=teacher))
    if teacher.is_eng:
        await state.update_data(teacher_type='ENG')
        await questions_start(message, state)
    else:
        await teacher_type_start(message)


async def teacher_type_start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(row_width=2).add(*[
        types.InlineKeyboardButton(L[f'teacher_type_{type_}'], callback_data=type_)
        for type_ in list(models.TEACHER_TYPE.keys())[:-1]
    ])
    await message.answer(L['choose_teacher_type'], reply_markup=keyboard)
    await PollStates.teacher_type.set()


@dp.callback_query_handler(state=PollStates.teacher_type)
async def teacher_type_query_handler(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(teacher_type=query.data)
    await query.message.delete()
    await questions_start(query.message, state)


async def questions_start(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        teacher_type = data['teacher_type']
        data['q2a'] = {}

        questions = models.Question.get_by_type(teacher_type)
        for question in questions:
            await message.answer(hbold(question.question_text) + '\n' * 2 + hitalic(question.answer_tip),
                                 reply_markup=question_keyboard(question, teacher_type))
            await asyncio.sleep(0.1)
            data['q2a'][question.id] = [None] * (2 if question.need_two_answers(teacher_type) else 1)
    await PollStates.questions.set()


@dp.callback_query_handler(state=PollStates.questions)
async def questions_handler(query: types.CallbackQuery, state: FSMContext):
    question_id, row_n, answer = json.loads(query.data)
    await query.answer()

    async with state.proxy() as data:
        data['q2a'][question_id][row_n] = answer
    keyboard = question_keyboard(models.Question.objects.get(id=question_id),
                                 teacher_type=data['teacher_type'], answers=data['q2a'][question_id])
    with suppress(exceptions.MessageNotModified):
        await query.message.edit_reply_markup(keyboard)

    if not [1 for answers in data['q2a'].values() for answer in answers if answer is None]:
        await open_question_start(query.message)


async def open_question_start(message: types.Message):
    await message.answer(L['open_question_text'], reply_markup=types.ForceReply())
    await PollStates.open_question.set()


@dp.message_handler(state=PollStates.open_question)
async def open_question_query_handler(message: types.Message, state: FSMContext):
    if message.text == '/skip':
        await state.update_data(open_q=None)
        await save_to_db(message, state)
    elif message.text == '/confirm':
        await save_to_db(message, state)
    else:
        await state.update_data(open_q=message.text)
        await message.answer(L['confirm_open_question_text'])


async def save_to_db(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            models.Result.add(
                message.from_user.id, data['teacher_n_group'], data['teacher_type'], data['open_q'], data['q2a'])
        except Exception:
            await message.answer(L['result_save_error'])
            raise
        else:
            await message.answer(L['result_save_success'])
    await state.finish()