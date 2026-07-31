async def edit_menu(query, text, reply_markup=None, parse_mode="Markdown"):
    """query.message can be a photo (logo/QR) or plain text — edit the right field."""
    if query.message.photo:
        await query.edit_message_caption(caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode=parse_mode, reply_markup=reply_markup)
