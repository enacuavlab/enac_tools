
local xml2lua = require("xml2lua")
print("xml2lua v" .. xml2lua._VERSION.."\n")
local handler = require("xmlhandler.tree")


local function load_messages(filename)
    local xml = xml2lua.loadFile(filename)
    local parser = xml2lua.parser(handler)
    parser:parse(xml)
    local classes = handler.root.protocol.msg_class

    messages = {}
  
    if classes == nil then
     return
    end

    for _, class in pairs(classes) do
        local class_name = class._attr.name
        local class_id = class._attr.id
        messages[class_id] = {}
        messages[class_id].name = class_name
        messages[class_id].msgs = {}
        for _, msg in pairs(class.message) do
            local msg_name = msg._attr.name
            local msg_id = msg._attr.id
            messages[class_id].msgs[msg_id] = {}
            messages[class_id].msgs[msg_id].name = msg_name
            messages[class_id].msgs[msg_id].fields = {}
            if msg.field ~= nil then
                for i, field in pairs(msg.field) do
                    if field._attr ~= nil then
                      messages[class_id].msgs[msg_id].fields[i] = {}
                      messages[class_id].msgs[msg_id].fields[i].name=field._attr.name
                      messages[class_id].msgs[msg_id].fields[i].type=field._attr.type
                    else
                        print(" BUG for msg" .. msg_name .. " field._attr is nil ! (happens when there is only one field?)")
                    end
                end
            else
                print("No fields for message " .. msg_name .. ".")
            end
        end
    end
    
    function messages:get_names(class_id, msg_id)
        local sci = tostring(class_id)
        local smi = tostring(msg_id)
        if self[sci] ~= nil and self[sci].msgs[smi] ~= nil then
            return self[sci].name, self[sci].msgs[smi].name
            --for _, f in pairs(msg_def.fields) do
            --    print("  " .. f.name .. ": " .. f.type)
            --end
        end
    end
    
    return messages
end




local messages = load_messages(os.getenv("PAPARAZZI_HOME") .. "/var/messages.xml")




local pprzlink_protocol = Proto("Pprzlink", "Pprzlink protocol")

local prefs = pprzlink_protocol.prefs

prefs.udp_rx_port = Pref.uint( "UDP receiving Port (default 4242)", 4242)
prefs.udp_tx_port = Pref.uint( "UDP sending Port (default 4243)", 4243)



p_stx = ProtoField.uint8("pprzlink.stx", "STX", base.HEX)
p_message_length = ProtoField.uint8("pprzlink.message_length", "messageLength", base.DEC)
p_src = ProtoField.uint8("pprzlink.src", "source", base.DEC)
p_dst = ProtoField.uint8("pprzlink.dst", "destination", base.DEC)
p_class = ProtoField.uint8("pprzlink.class", "class", base.DEC, nil, 0x0f)
p_component = ProtoField.uint8("pprzlink.component", "component", base.DEC, nil, 0xf0)
p_msg_id = ProtoField.uint8("pprzlink.msg_id", "Msg ID", base.DEC)

p_payload = ProtoField.bytes("pprzlink.payload", "Msg payload")

p_chk = ProtoField.uint16("pprzlink.checskum", "checksum", base.HEX)


pprzlink_protocol.fields = {
    p_stx,
    p_message_length,
    p_src,
    p_dst,
    p_class,
    p_component,
    p_msg_id,
    p_payload,
    p_chk
}

function pprzlink_protocol.dissector(buffer, pinfo, tree)
    lenght = buffer:len()
    if lenght == 0 then return end
    local stx = buffer(0,1):le_uint()
    if stx ~= 0x99 then return end
    
    local class_id = buffer(4,1):le_uint()
    local msg_id = buffer(5,1):le_uint()
    local class_name, msg_name = messages:get_names(class_id, msg_id)

    pinfo.cols.protocol = pprzlink_protocol.name
    local subtree = tree:add(pprzlink_protocol, buffer(), "Pprzlink protocol data, Msg: " .. msg_name)
    
    subtree:add_le(p_stx, buffer(0,1))
    subtree:add_le(p_message_length, buffer(1,1))
    subtree:add_le(p_src, buffer(2,1))
    subtree:add_le(p_dst, buffer(3,1))
    subtree:add_le(p_class, buffer(4,1)):append_text(" (" .. class_name .. ")")
    subtree:add_le(p_component, buffer(4,1))
    subtree:add_le(p_msg_id, buffer(5,1)):append_text(" (" .. msg_name .. ")")
    

    local payload_len = buffer(1,1):le_uint() - 8
    if payload_len > 0 then
        subtree:add(p_payload, buffer(6, payload_len))
    end
    
    local chk_offset = buffer:len()-2
    local cka = 0
    local ckb = 0
    for i=1, lenght-3 do
        local b = buffer(i,1):uint()
        cka = (cka + b) % 256
        ckb = (ckb + cka) % 256
    end
    
    if cka == buffer(chk_offset,1):uint() and ckb == buffer(chk_offset+1,1):uint() then
        subtree:add(p_chk, buffer(chk_offset, 2))
    else
        subtree:add(p_chk, buffer(chk_offset, 2)):add_expert_info(PI_CHECKSUM, PI_ERROR, "checksum mismatch!")
    end
    
end


local udp_dissector_table = DissectorTable.get("udp.port")

function pprzlink_protocol.init() --Preference Update
    udp_dissector_table:add(prefs.udp_rx_port, pprzlink_protocol)
    udp_dissector_table:add(prefs.udp_tx_port, pprzlink_protocol)
end


