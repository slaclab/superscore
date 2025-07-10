"""
Home for functions that return an Entry or Root

Do not place pytest fixtures here, as these callables may be used in running
demo instances.  Instead create corresponding fixtures in conftest.py directly
"""

from copy import deepcopy
from uuid import UUID

from superscore.model import (Collection, Parameter, Readback, Root, Setpoint,
                              Severity, Snapshot, Status)


def linac_data() -> Root:
    lasr_gunb_pv1 = Parameter(
        uuid="5544c58f-88b6-40aa-9076-f180a44908f5",
        pv_name="LASR:GUNB:TEST1",
        description="First LASR pv in GUNB",
    )

    now = lasr_gunb_pv1.creation_time

    lasr_gunb_pv2 = Parameter(
        uuid="7cb3760c-793c-4974-a8ae-778e5d491e4a",
        pv_name="LASR:GUNB:TEST2",
        description="Second LASR pv in GUNB",
        creation_time=now,
    )

    mgnt_gunb_pv = Parameter(
        uuid="930b137f-5ae2-470e-8b82-c4b4eb7e639e",
        pv_name="MGNT:GUNB:TEST0",
        description="Only MGNT pv in GUNB",
        creation_time=now,
    )

    vac_gunb_pv1 = Parameter(
        uuid="8f3ac401-68f8-4def-b65a-3c8116c80ba7",
        pv_name="VAC:GUNB:TEST1",
        description="First VAC pv in GUNB",
        creation_time=now,
    )

    vac_gunb_pv2 = Parameter(
        uuid="06448272-cd38-4bb4-9b8d-292673a497e9",
        pv_name="VAC:GUNB:TEST2",
        description="Second VAC pv in GUNB",
        creation_time=now,
    )

    vac_l0b_pv = Parameter(
        uuid="5ec33c74-7f4c-4905-a106-44fbfe138140",
        pv_name="VAC:L0B:TEST0",
        description="Only VAC pv in L0B",
        creation_time=now,
    )

    vac_bsy_pv = Parameter(
        uuid="030786df-153b-4d29-bc1f-66deeb116724",
        pv_name="VAC:BSY:TEST0",
        description="Only VAC pv in BSY",
        creation_time=now,
    )

    vac_li10_pv = Parameter(
        uuid="2c83a9be-bec6-4436-8233-79df300af670",
        pv_name="VAC:LI10:TEST0",
        description="Only VAC pv in LI10",
        creation_time=now,
    )

    lasr_in10_pv = Parameter(
        uuid="f802dee1-569b-4c6b-a32f-c213af10ecec",
        pv_name="LASR:IN10:TEST0",
        description="Only laser pv in IN10",
        creation_time=now,
    )

    lasr_in20_pv = Parameter(
        uuid="a13ef8a5-b8df-4caa-80f5-395b16eaa5f1",
        pv_name="LASR:IN20:TEST0",
        description="Only laser pv in IN20",
        creation_time=now,
    )

    vac_li21_pv = Parameter(
        uuid="8dba63d5-98e8-4647-ae44-ff0a38a4805d",
        pv_name="VAC:LI21:TEST0",
        description="Only VAC pv in LI21",
        creation_time=now,
    )

    lasr_gunb_value1 = Setpoint(
        uuid="927ef6cb-e45f-4175-aa5f-6c6eec1f3ae4",
        pv_name=lasr_gunb_pv1.pv_name,
        description=lasr_gunb_pv1.description,
        data="Off",
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    now = lasr_gunb_value1.creation_time

    lasr_gunb_value2 = Setpoint(
        uuid="a221f6fa-6bc1-40ad-90fb-2041c29a5f67",
        pv_name=lasr_gunb_pv2.pv_name,
        description=lasr_gunb_pv2.description,
        creation_time=now,
        data=5,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    mgnt_gunb_value = Setpoint(
        uuid="502d9fc3-455a-47ea-8c48-e1a26d4d3350",
        pv_name=mgnt_gunb_pv.pv_name,
        description=mgnt_gunb_pv.description,
        creation_time=now,
        data=True,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_gunb_value1 = Setpoint(
        uuid="cc187dbf-fa41-49d7-8c7b-49c8989c6a2f",
        pv_name=vac_gunb_pv1.pv_name,
        description=vac_gunb_pv1.description,
        creation_time=now,
        data="Ion Pump",
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_gunb_value2 = Setpoint(
        uuid="7c87960d-8b58-4b29-8d5e-e1f3223e356a",
        pv_name=vac_gunb_pv2.pv_name,
        description=vac_gunb_pv2.description,
        creation_time=now,
        data=False,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_l0b_value = Setpoint(
        uuid="2ef43192-40c9-4e79-96e7-2d7f6df58cd9",
        pv_name=vac_l0b_pv.pv_name,
        description=vac_l0b_pv.description,
        creation_time=now,
        data=-10,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_bsy_value = Setpoint(
        uuid="6bebcb59-884f-4e68-927d-f3053effd698",
        pv_name=vac_bsy_pv.pv_name,
        description=vac_bsy_pv.description,
        creation_time=now,
        data="",
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_li10_value = Setpoint(
        uuid="ee56d60b-b8b9-447d-b857-6117e22f1462",
        pv_name=vac_li10_pv.pv_name,
        description=vac_li10_pv.description,
        creation_time=now,
        data=.25,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    lasr_in10_value = Setpoint(
        uuid="fb809d22-76fb-493e-b7f2-b522319e5e2f",
        pv_name=lasr_in10_pv.pv_name,
        description=lasr_in10_pv.description,
        creation_time=now,
        data=645.26,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    lasr_in20_value = Setpoint(
        uuid="4d2f7bf2-af71-492b-8528-ba9b6e3ab964",
        pv_name=lasr_in20_pv.pv_name,
        description=lasr_in20_pv.description,
        creation_time=now,
        data=0,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_li21_readback = Readback(
        uuid="de66d08e-09c3-4c45-8978-900e51d00248",
        pv_name=vac_li21_pv.pv_name,
        description=vac_li21_pv.description,
        creation_time=now,
        data=0.0,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    vac_li21_setpoint = Setpoint(
        uuid="4bffe9a5-f198-41d8-90ab-870d1b5a325b",
        pv_name=vac_li21_pv.pv_name,
        description=vac_li21_pv.description,
        creation_time=now,
        data=5.0,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
        readback=vac_li21_readback,
    )

    all_snapshot = Snapshot(
        uuid="06282731-33ea-4270-ba14-098872e627dc",
        description="All three facilities in the SLAC LINAC: LCLS-NC, FACET, and LCLS-SC",
        title="Accelerator Directorate",
        children=[
            lasr_gunb_value1,
            lasr_gunb_value2,
            mgnt_gunb_value,
            vac_gunb_value1,
            vac_gunb_value2,
            vac_l0b_value,
            vac_bsy_value,
            vac_li10_value,
            lasr_in10_value,
            lasr_in20_value,
            vac_li21_readback,
            vac_li21_setpoint,
        ],
    )

    tags = {
        0: [
            "Dest",
            "Which endpoint the beam is directed towards",
            {
                0: "SXR",
                1: "HXR",
            }
        ],
    }

    hxr_pulse = Parameter(
        uuid="653cf3f8-56d1-4409-b8d2-a31be09a9a20",
        pv_name="DEST:HXR:PLSI",
        description="HXR Pulse Intensity",
        creation_time=now,
        read_only=True,
    )

    sxr_pulse = Parameter(
        uuid="3ed979c7-50ed-402f-9b6e-f3e5ebc1a18c",
        pv_name="DEST:SXR:PLSI",
        description="SXR Pulse Intensity",
        creation_time=now,
        read_only=True,
    )

    hxr_edes = Parameter(
        uuid="006cbc48-5ead-4da7-9b3c-d4f4792c3bad",
        pv_name="DEST:HXR:EDES",
        description="HXR Energy Target",
        creation_time=now,
        read_only=True,
    )

    sxr_edes = Parameter(
        uuid="51179e2b-53e1-417a-b6a9-4f20605d19bb",
        pv_name="DEST:SXR:EDES",
        description="SXR Energy Target",
        creation_time=now,
        read_only=True,
    )

    hxr_pulse_readback = Readback(
        uuid="40451e72-575a-4069-a953-2d21af45c95f",
        pv_name=hxr_pulse.pv_name,
        description=hxr_pulse.description,
        data=9.829,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    sxr_pulse_readback = Readback(
        uuid="60819a50-db1b-415c-acf3-c57a2df6e5fe",
        pv_name=sxr_pulse.pv_name,
        description=sxr_pulse.description,
        data=3.5,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    hxr_edes_readback = Readback(
        uuid="8df5c8f7-9dc9-4555-9b17-d089551dafcc",
        pv_name=hxr_edes.pv_name,
        description=hxr_edes.description,
        data=9.829,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    sxr_edes_readback = Readback(
        uuid="61d3311b-fb72-40b7-bfac-9746e787abc9",
        pv_name=sxr_edes.pv_name,
        description=sxr_edes.description,
        data=3.5,
        status=Status.NO_ALARM,
        severity=Severity.NO_ALARM,
    )

    all_snapshot.meta_pvs = [
        hxr_pulse_readback,
        sxr_pulse_readback,
        hxr_edes_readback,
        sxr_edes_readback
    ]

    return Root(
        entries=[
            all_snapshot,
            lasr_gunb_pv1,
            lasr_gunb_pv2,
            mgnt_gunb_pv,
            vac_gunb_pv1,
            vac_gunb_pv2,
            vac_l0b_pv,
            vac_bsy_pv,
            vac_li10_pv,
            lasr_in10_pv,
            lasr_in20_pv,
            vac_li21_pv,
        ],
        tag_groups=tags,
        meta_pvs=[hxr_pulse, hxr_edes, sxr_pulse, sxr_edes]
    )


def linac_with_comparison_snapshot() -> Root:
    root = linac_data()
    original_snapshot = root.entries[0]
    snapshot = deepcopy(original_snapshot)
    snapshot.title = 'AD Comparison'
    snapshot.description = ('A snapshot with different values and statuses to compare '
                            'to the "standard" snapshot')
    snapshot.uuid = UUID("8e0b1916-912a-457e-8ff9-4478b8018cec")

    (
        lasr_gunb_value1,
        lasr_gunb_value2,
        mgnt_gunb_value,
        vac_gunb_value1,
        vac_gunb_value2,
        vac_l0b_value,
        vac_bsy_value,
        vac_li10_value,
        lasr_in10_value,
        lasr_in20_value,
        vac_li21_readback,
        vac_li21_setpoint
    ) = snapshot.children

    lasr_in20_value.uuid = UUID('ef321662-f98e-4511-b9b0-6f2d8037c302')
    lasr_in20_value.data = -1
    lasr_in20_value.severity = Severity.MAJOR

    vac_li21_setpoint.uuid = UUID('e977f215-a7c9-4caf-8f91-d2783f3e4a88')
    vac_li21_setpoint.data = 0.0
    vac_li21_setpoint.severity = Severity.MINOR
    vac_li21_readback.uuid = UUID('949a9837-95bd-4ca0-8dad-f478f57143dd')

    vac_bsy_value.uuid = UUID('b976bac4-d68b-45b0-a519-e0307a60b052')
    vac_bsy_value.data = "lasdjfjasldfj"

    lasr_in10_value.uuid = UUID('21bf36a2-002c-49fe-a7c3-eade33d62dfd')
    lasr_in10_value.data = 640.68
    lasr_in10_value.status = Status.CALC

    vac_li10_value.uuid = UUID('732cb745-482f-40a7-b83c-d7f2d4ed2305')
    vac_li10_value.data = .27

    vac_gunb_value1.uuid = UUID('0e6c4d09-2a77-4ac2-b57a-fc9c049e9063')
    vac_gunb_value2.uuid = UUID('d2a45d2b-bb7c-4ccb-a2e3-5e5a44c7dd30')
    vac_gunb_value2.data = True

    mgnt_gunb_value.uuid = UUID('61c7ac48-77eb-430c-a86b-52c1267f8ef0')

    lasr_gunb_value1.uuid = UUID('4719d31c-62fc-490b-9729-7889f0b79df8')
    lasr_gunb_value1.severity = Severity.INVALID
    lasr_gunb_value2.uuid = UUID('bced6e63-f4f8-4ab5-9256-66a7da66b160')

    vac_l0b_value.uuid = UUID('de169754-cafd-4f38-9f26-cf92039e75d8')
    vac_l0b_value.data = -15
    vac_l0b_value.severity = Severity.MINOR

    root.entries.append(snapshot)
    return root


def setpoint_with_readback() -> Setpoint:
    """
    A simple setpoint-readback value pair
    """
    readback = Readback(
        uuid="7b30ddba-9fae-4691-988c-07384c29fe22",
        pv_name="RBV",
        description="A readback PV",
        data=False,
    )
    setpoint = Setpoint(
        uuid="418ed1ab-f1cf-4188-8f4c-ae7cbaf00e6c",
        pv_name="SET",
        description="A setpoint PV",
        data=True,
        readback=readback,
    )
    return setpoint


def parameter_with_readback() -> Parameter:
    """
    A simple setpoint-readback parameter pair
    """
    readback = Parameter(
        uuid="64772c61-c117-445b-b0c8-4c17fd1625d9",
        pv_name="RBV",
        description="A readback PV",
        read_only=True,
    )
    setpoint = Parameter(
        uuid="b508344d-1fe9-473b-8d43-9499d0e8e23f",
        pv_name="SET",
        description="A setpoint PV",
        readback=readback,
    )
    return setpoint


def simple_snapshot() -> Snapshot:
    snap = Snapshot(description='various types', title='types collection')
    snap.children.append(Setpoint(pv_name="MY:FLOAT"))
    snap.children.append(Setpoint(pv_name="MY:INT"))
    snap.children.append(Setpoint(pv_name="MY:ENUM"))
    return snap


def simple_comparison_snapshot() -> Snapshot:
    snap = simple_snapshot()
    snap.children.pop(0)
    snap.children[0].data = 1
    snap.children.append(Setpoint(pv_name="MY:NEW:ENUM"))
    return snap


def sample_database() -> Root:
    """
    A sample superscore database, including all the Entry types.
    Corresponds to a caproto.ioc_examples.fake_motor_record, which mimics an IMS
    motor record
    """
    root = Root()
    param_1 = Parameter(
        description='parameter 1 in root',
        pv_name='MY:MOTOR:mtr1.ACCL'
    )
    root.entries.append(param_1)
    value_1 = Setpoint.from_parameter(
        origin=param_1,
        data=2,
    )
    root.entries.append(value_1)
    coll_1 = Collection(
        title='collection 1',
        description='collection 1 defining some motor fields',
    )
    snap_1 = Snapshot(
        title='snapshot 1',
        description='Snapshot 1 created from collection 1',
    )
    for fld, data in zip(['ACCL', 'VELO', 'PREC'], [2, 2, 6]):  # Defaults[1, 1, 3]
        sub_param = Parameter(
            description=f'motor field {fld}',
            pv_name=f'MY:PREFIX:mtr1.{fld}'
        )
        sub_value = Setpoint.from_parameter(
            origin=sub_param,
            data=data,
        )
        coll_1.children.append(sub_param)
        snap_1.children.append(sub_value)
    root.entries.append(coll_1)
    root.entries.append(snap_1)

    return root
